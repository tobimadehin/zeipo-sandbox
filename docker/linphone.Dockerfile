FROM ubuntu:22.04

# Avoid prompts during install
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies and linphone
RUN apt-get update && apt-get install -y \
    linphone \
    libcanberra-gtk-module \
    libcanberra-gtk3-module \
    x11-apps \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Run Linphone GUI by default
CMD ["linphone"]

