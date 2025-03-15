# app/db/models.py
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base
import uuid

class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True)
    phone_number = Column(String, unique=True, nullable=False)
    preferred_language = Column(String)
    created_at = Column(DateTime, default=func.now())
    last_activity = Column(DateTime)
    
    calls = relationship("CallSession", back_populates="customer")

class CallSession(Base):
    __tablename__ = "call_sessions"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String, unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    customer_id = Column(Integer, ForeignKey("customers.id"))
    start_time = Column(DateTime, nullable=False, default=func.now())
    end_time = Column(DateTime)
    duration_seconds = Column(Integer)
    recording_url = Column(String)
    handled_by_ai = Column(Boolean, default=True)
    escalated = Column(Boolean, default=False)
    
    customer = relationship("Customer", back_populates="calls")
    transcriptions = relationship("Transcription", back_populates="call_session")
    language_detections = relationship("LanguageDetection", back_populates="call_session")
    call_intents = relationship("CallIntent", back_populates="call_session")
    entities = relationship("Entity", back_populates="call_session")

class LanguageDetection(Base):
    __tablename__ = "language_detections"
    
    id = Column(Integer, primary_key=True)
    call_session_id = Column(Integer, ForeignKey("call_sessions.id"), nullable=False)
    detected_language = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    detection_time = Column(DateTime, default=func.now())
    
    call_session = relationship("CallSession", back_populates="language_detections")

class Transcription(Base):
    __tablename__ = "transcriptions"
    
    id = Column(Integer, primary_key=True)
    call_session_id = Column(Integer, ForeignKey("call_sessions.id"), nullable=False)
    segment_start_time = Column(Float, nullable=False)
    segment_end_time = Column(Float)
    transcript = Column(Text, nullable=False)
    speaker = Column(String, nullable=False)
    
    call_session = relationship("CallSession", back_populates="transcriptions")

class Intent(Base):
    __tablename__ = "intents"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text)
    
    call_intents = relationship("CallIntent", back_populates="intent")

class CallIntent(Base):
    __tablename__ = "call_intents"
    
    id = Column(Integer, primary_key=True)
    call_session_id = Column(Integer, ForeignKey("call_sessions.id"), nullable=False)
    intent_id = Column(Integer, ForeignKey("intents.id"), nullable=False)
    confidence = Column(Float, nullable=False)
    detection_time = Column(DateTime, default=func.now())
    
    call_session = relationship("CallSession", back_populates="call_intents")
    intent = relationship("Intent", back_populates="call_intents")

class Entity(Base):
    __tablename__ = "entities"
    
    id = Column(Integer, primary_key=True)
    call_session_id = Column(Integer, ForeignKey("call_sessions.id"), nullable=False)
    entity_type = Column(String, nullable=False)
    entity_value = Column(Text, nullable=False)
    extraction_time = Column(DateTime, default=func.now())
    
    call_session = relationship("CallSession", back_populates="entities")
    