# src/analytics/metrics.py
import time
import logging
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime
from prometheus_client import Counter, Histogram, Gauge, Summary, start_http_server, push_to_gateway
import sqlalchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from Levenshtein import distance

from config import settings
from db.models import CallSession
from static.constants import logger

class MetricsService:
    """Centralized service for collecting and exposing metrics."""
    
    def __init__(self, app_name: str = "zeipo_metrics", expose_port: int = 9091):
        self.app_name = app_name
        self.start_time = time.time()
        self.expose_port = expose_port
        self.session_metrics = {}  # Track metrics by session ID
        
        # Initialize DB connection for analytics
        self.analytics_engine = create_engine(settings.ANALYTICS_DB_URL) # TODO: Setup real DB
        self.AnalyticsSession = sessionmaker(autocommit=False, autoflush=False, bind=self.analytics_engine)
        
        # Initialize Prometheus metrics
        # Call metrics
        self.call_counter = Counter(
            f'{app_name}_calls_total', 
            'Total number of calls', 
            ['provider', 'status']
        )
        
        self.call_duration = Histogram(
            f'{app_name}_call_duration_seconds', 
            'Call duration in seconds',
            ['provider'],
            buckets=[5, 10, 30, 60, 120, 300, 600, 1800, 3600]  # From 5s to 1hr
        )
        
        # Speech processing metrics
        self.transcription_latency = Histogram(
            f'{app_name}_transcription_latency_seconds', 
            'Time to transcribe audio chunk',
            ['model', 'language'],
            buckets=[0.1, 0.5, 1, 2, 5, 10, 20]  # 100ms to 20s
        )
        
        self.speech_segments = Counter(
            f'{app_name}_speech_segments_total', 
            'Total number of speech segments processed',
            ['is_final']
        )
        
        self.wer_gauge = Gauge(
            f'{app_name}_word_error_rate',
            'Word Error Rate (lower is better)',
            ['model']
        )
        
        # NLU metrics
        self.intent_detections = Counter(
            f'{app_name}_intent_detections_total', 
            'Total number of intent detections',
            ['intent', 'confidence_bucket']
        )
        
        self.entity_extractions = Counter(
            f'{app_name}_entity_extractions_total', 
            'Total number of entity extractions',
            ['entity_type']
        )
        
        self.intent_agreement = Gauge(
            f'{app_name}_intent_agreement_ratio',
            'Ratio of agreement between primary and verification intent detection',
            []
        )
        
        # TTS metrics
        self.tts_synthesis_latency = Histogram(
            f'{app_name}_tts_synthesis_seconds', 
            'Time to synthesize speech',
            ['provider', 'voice'],
            buckets=[0.1, 0.25, 0.5, 1, 2, 5]  # 100ms to 5s
        )
        
        # User experience metrics
        self.silence_ratio = Gauge(
            f'{app_name}_silence_ratio', 
            'Ratio of silence to speech in calls',
            ['session_id']
        )
        
        self.end_to_end_latency = Histogram(
            f'{app_name}_end_to_end_latency_seconds',
            'Time from user speech to system response',
            [],
            buckets=[0.5, 1, 2, 3, 5, 10]  # 500ms to 10s
        )
        
        # Quality score metrics
        self.quality_score = Gauge(
            f'{app_name}_quality_score',
            'Overall Zeipo Quality Score',
            []
        )
        
        self.category_scores = Gauge(
            f'{app_name}_category_scores',
            'Quality scores by category',
            ['category']
        )
        
        # System metrics
        self.system_errors = Counter(
            f'{app_name}_errors_total', 
            'Total number of system errors',
            ['component', 'error_type']
        )
        
        # Start metrics server or push gateway thread
        self._start_metrics_exposure()
        
        # Start periodic flush to database
        self._start_db_flush()
        
        logger.info(f"Metrics service initialized with {len(self.__dict__)} metrics")

    def _start_metrics_exposure(self):
        """Start exposing metrics via HTTP server or push gateway."""
        try:
            # Try to start HTTP server
            start_http_server(self.expose_port)
            logger.info(f"Metrics server started on port {self.expose_port}")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {str(e)}")
            # Fall back to push gateway if specified in settings
            if hasattr(settings, "PROMETHEUS_PUSHGATEWAY_URL") and settings.PROMETHEUS_PUSHGATEWAY_URL: # TODO: Add gateway URL to settings
                logger.info(f"Using push gateway at {settings.PROMETHEUS_PUSHGATEWAY_URL}")
                # Start push thread
                self._start_push_thread()
            else:
                logger.warning("No push gateway configured, metrics will not be exposed")
    
    def _start_push_thread(self):
        """Start a background thread to push metrics to Prometheus push gateway."""
        def push_metrics():
            while True:
                try:
                    push_to_gateway(
                        settings.PROMETHEUS_PUSHGATEWAY_URL, 
                        job=self.app_name, 
                        registry=None  # Use default registry
                    )
                except Exception as e:
                    logger.error(f"Error pushing metrics: {str(e)}")
                time.sleep(15)  # Push every 15 seconds
                
        thread = threading.Thread(target=push_metrics, daemon=True)
        thread.start()
    
    def _start_db_flush(self):
        """Start a background thread to flush aggregated metrics to database."""
        def flush_metrics():
            while True:
                try:
                    # Copy session metrics to avoid modification during iteration
                    sessions_to_flush = dict(self.session_metrics)
                    
                    if sessions_to_flush:
                        # Open DB session
                        db = self.AnalyticsSession()
                        
                        for session_id, metrics in sessions_to_flush.items():
                            if metrics.get("completed", False):
                                # Store in analytics DB
                                self._store_session_metrics(db, session_id, metrics)
                                # Remove from in-memory storage
                                self.session_metrics.pop(session_id, None)
                        
                        db.commit()
                        db.close()
                except Exception as e:
                    logger.error(f"Error flushing metrics to database: {str(e)}")
                
                # Sleep for 60 seconds
                time.sleep(60)
        
        thread = threading.Thread(target=flush_metrics, daemon=True)
        thread.start()
    
    def _store_session_metrics(self, db, session_id: str, metrics: Dict[str, Any]):
        """Store session metrics in the analytics database."""
        try:
            # Insert call metrics
            db.execute(
                sqlalchemy.text("""
                INSERT INTO call_metrics 
                (time, session_id, provider, duration_seconds, status, 
                 transcription_count, intent_count, silence_ratio, response_count)
                VALUES 
                (:time, :session_id, :provider, :duration, :status,
                 :transcription_count, :intent_count, :silence_ratio, :response_count)
                """),
                {
                    "time": datetime.now(),
                    "session_id": session_id,
                    "provider": metrics.get("provider", "unknown"),
                    "duration": metrics.get("duration_seconds", 0),
                    "status": metrics.get("status", "unknown"),
                    "transcription_count": metrics.get("transcription_count", 0),
                    "intent_count": metrics.get("intent_count", 0),
                    "silence_ratio": metrics.get("silence_ratio", 0),
                    "response_count": metrics.get("response_count", 0)
                }
            )
            
            # Insert transcription quality if available
            if "transcription_quality" in metrics:
                for quality in metrics["transcription_quality"]:
                    db.execute(
                        sqlalchemy.text("""
                        INSERT INTO transcription_quality
                        (time, session_id, streaming_text, final_text, 
                         word_error_rate, character_error_rate, processing_time_ms, audio_duration_ms)
                        VALUES
                        (:time, :session_id, :streaming_text, :final_text,
                         :wer, :cer, :processing_time, :audio_duration)
                        """),
                        {
                            "time": datetime.now(),
                            "session_id": session_id,
                            "streaming_text": quality.get("streaming_text", ""),
                            "final_text": quality.get("final_text", ""),
                            "wer": quality.get("wer", 0),
                            "cer": quality.get("cer", 0),
                            "processing_time": quality.get("processing_time_ms", 0),
                            "audio_duration": quality.get("audio_duration_ms", 0)
                        }
                    )
            
            # Insert intent metrics if available
            if "intent_metrics" in metrics:
                for intent in metrics["intent_metrics"]:
                    db.execute(
                        sqlalchemy.text("""
                        INSERT INTO intent_metrics
                        (time, session_id, text, detected_intent,
                         verification_intent, agreement, confidence, entity_count)
                        VALUES
                        (:time, :session_id, :text, :detected_intent,
                         :verification_intent, :agreement, :confidence, :entity_count)
                        """),
                        {
                            "time": datetime.now(),
                            "session_id": session_id,
                            "text": intent.get("text", ""),
                            "detected_intent": intent.get("detected_intent", ""),
                            "verification_intent": intent.get("verification_intent", ""),
                            "agreement": intent.get("agreement", False),
                            "confidence": intent.get("confidence", 0),
                            "entity_count": intent.get("entity_count", 0)
                        }
                    )
            
        except Exception as e:
            logger.error(f"Error storing metrics for session {session_id}: {str(e)}")
            # Don't raise, just log - we don't want metrics errors to affect the main application
    
    # Call tracking methods
    def record_call_start(self, session_id: str, provider: str) -> None:
        """Record the start of a new call."""
        self.call_counter.labels(provider=provider, status="started").inc()
        
        # Initialize session metrics
        self.session_metrics[session_id] = {
            "start_time": time.time(),
            "provider": provider,
            "transcription_count": 0,
            "intent_count": 0,
            "response_count": 0,
            "transcription_quality": [],
            "intent_metrics": [],
            "completed": False
        }
    
    def record_call_end(self, session_id: str, provider: str, duration: float, status: str) -> None:
        """Record the end of a call with its duration and status."""
        self.call_counter.labels(provider=provider, status=status).inc()
        self.call_duration.labels(provider=provider).observe(duration)
        
        # Update session metrics
        if session_id in self.session_metrics:
            metrics = self.session_metrics[session_id]
            metrics["duration_seconds"] = duration
            metrics["status"] = status
            metrics["completed"] = True
            metrics["end_time"] = time.time()
    
    # Speech processing methods
    def record_transcription(self, 
                            session_id: str,
                            model: str, 
                            language: str, 
                            duration: float, 
                            text_length: int, 
                            is_final: bool) -> None:
        """Record a speech transcription event."""
        self.transcription_latency.labels(model=model, language=language or "auto").observe(duration)
        self.speech_segments.labels(is_final=str(is_final)).inc()
        
        # Update session metrics
        if session_id in self.session_metrics:
            self.session_metrics[session_id]["transcription_count"] += 1
    
    def record_transcription_quality(self, 
                                    session_id: str,
                                    streaming_text: str, 
                                    final_text: str, 
                                    wer: float,
                                    processing_time_ms: int,
                                    audio_duration_ms: int) -> None:
        """Record transcription quality metrics."""
        # Update WER gauge
        model_name = self.session_metrics.get(session_id, {}).get("model", "unknown")
        self.wer_gauge.labels(model=model_name).set(wer)
        
        # Calculate character error rate
        cer = distance(streaming_text, final_text) / max(len(final_text), 1)
        
        # Store quality metrics for this session
        if session_id in self.session_metrics:
            quality_metrics = {
                "streaming_text": streaming_text,
                "final_text": final_text,
                "wer": wer,
                "cer": cer,
                "processing_time_ms": processing_time_ms,
                "audio_duration_ms": audio_duration_ms,
                "timestamp": time.time()
            }
            
            self.session_metrics[session_id]["transcription_quality"].append(quality_metrics)
    
    # NLU methods
    def record_intent_detection(self, 
                                session_id: str,
                                text: str,
                                intent: str, 
                                confidence: float,
                                verification_intent: Optional[str] = None,
                                entity_count: int = 0) -> None:
        """Record an intent detection event."""
        # Bucket confidence into ranges for better visualization
        confidence_bucket = f"{int(confidence * 10) / 10:.1f}"
        self.intent_detections.labels(intent=intent, confidence_bucket=confidence_bucket).inc()
        
        # Record entities
        if entity_count > 0:
            self.entity_extractions.labels(entity_type="any").inc(entity_count)
        
        # Record intent agreement if verification intent is provided
        if verification_intent:
            agreement = intent == verification_intent
            
            # Store intent metrics for this session
            if session_id in self.session_metrics:
                intent_metrics = {
                    "text": text,
                    "detected_intent": intent,
                    "verification_intent": verification_intent,
                    "agreement": agreement,
                    "confidence": confidence,
                    "entity_count": entity_count,
                    "timestamp": time.time()
                }
                
                self.session_metrics[session_id]["intent_metrics"].append(intent_metrics)
                self.session_metrics[session_id]["intent_count"] += 1
        
    def record_entity_extraction(self, entity_type: str, count: int = 1) -> None:
        """Record entity extraction events."""
        self.entity_extractions.labels(entity_type=entity_type).inc(count)
    
    # TTS methods
    def record_tts_synthesis(self, 
                           provider: str, 
                           voice: str, 
                           duration: float, 
                           text_length: int) -> None:
        """Record a TTS synthesis event."""
        self.tts_synthesis_latency.labels(provider=provider, voice=voice).observe(duration)
    
    # User experience metrics
    def record_end_to_end_latency(self, latency_seconds: float) -> None:
        """Record the end-to-end latency from user input to system response."""
        self.end_to_end_latency.observe(latency_seconds)
    
    def update_silence_ratio(self, session_id: str, ratio: float) -> None:
        """Update the silence ratio for a call."""
        self.silence_ratio.labels(session_id=session_id).set(ratio)
        
        # Update session metrics
        if session_id in self.session_metrics:
            self.session_metrics[session_id]["silence_ratio"] = ratio
    
    def record_response(self, session_id: str) -> None:
        """Record that a response was generated and sent to the user."""
        # Update session metrics
        if session_id in self.session_metrics:
            self.session_metrics[session_id]["response_count"] += 1
    
    # Quality score methods
    def update_quality_score(self, score: int, category_scores: Dict[str, int]) -> None:
        """Update the Zeipo Quality Score."""
        self.quality_score.set(score)
        
        # Update individual category scores
        for category, score in category_scores.items():
            self.category_scores.labels(category=category).set(score)
    
    # Error tracking
    def record_error(self, component: str, error_type: str) -> None:
        """Record a system error."""
        self.system_errors.labels(component=component, error_type=error_type).inc()

# Initialize the global metrics service
metrics_service = MetricsService()
