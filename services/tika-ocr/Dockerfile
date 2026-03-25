FROM openjdk:17-slim

# Install Tesseract and OCR language support
RUN apt-get update && \
    apt-get install -y \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-osd \
        curl && \
    apt-get clean

# Set Tesseract data path
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata

# Download Tika server - use direct mirror
ENV TIKA_VERSION=3.2.1
RUN curl -L -o /tika-server.jar https://dlcdn.apache.org/tika/${TIKA_VERSION}/tika-server-standard-${TIKA_VERSION}.jar || \
    curl -L -o /tika-server.jar https://archive.apache.org/dist/tika/3.2.1/tika-server-standard-3.2.1.jar || \
    (echo "Failed to download Tika server!" && exit 1)

EXPOSE 9998

# Start Tika server
CMD ["java", "-jar", "/tika-server.jar", "--host", "0.0.0.0"]