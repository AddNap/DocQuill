#!/bin/bash
# Skrypt budujący emf-converter.jar

set -e  # Zatrzymaj przy błędzie

echo "========================================="
echo "  EMF Converter - Build Script"
echo "========================================="
echo ""

# Sprawdź czy Maven jest zainstalowany
if ! command -v mvn &> /dev/null; then
    echo "ERROR: Maven is not installed!"
    echo "Install with: sudo apt-get install maven"
    exit 1
fi

# Sprawdź czy Java jest zainstalowana
if ! command -v java &> /dev/null; then
    echo "ERROR: Java is not installed!"
    echo "Install with: sudo apt-get install openjdk-11-jdk"
    exit 1
fi

# Wyświetl wersje
echo "Maven version:"
mvn --version | head -n 1
echo ""
echo "Java version:"
java -version 2>&1 | head -n 1
echo ""

# Buduj projekt
echo "Building EMF Converter..."
mvn clean package

# Sprawdź czy JAR został utworzony
if [ -f "target/emf-converter.jar" ]; then
    echo ""
    echo "========================================="
    echo "  ✅ BUILD SUCCESSFUL!"
    echo "========================================="
    echo ""
    echo "JAR location: target/emf-converter.jar"
    echo "JAR size: $(du -h target/emf-converter.jar | cut -f1)"
    echo ""
    echo "Test the converter:"
    echo "  java -jar target/emf-converter.jar input.emf output.svg"
    echo ""
else
    echo ""
    echo "========================================="
    echo "  ❌ BUILD FAILED!"
    echo "========================================="
    echo "JAR file was not created."
    exit 1
fi

