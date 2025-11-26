# EMF to SVG Converter

Wysokiej jakości konwerter plików EMF/WMF do SVG używający **FreeHEP VectorGraphics**.

## 🎯 Dlaczego FreeHEP?

FreeHEP VectorGraphics został wybrany jako najlepsze rozwiązanie do konwersji EMF:

| Cecha | FreeHEP | Apache Batik | emf2svg |
|-------|---------|--------------|---------|
| **Wsparcie EMF** | ✅ Natywne | ⚠️ Ograniczone | ✅ Dobre |
| **Jakość** | 9/10 | 6/10 | 7/10 |
| **Rozmiar** | ~2-4 MB | ~8-15 MB | Mały binary |
| **Instalacja** | JAR (portable) | JAR (duży) | apt/compile |
| **Cross-platform** | ✅ Java | ✅ Java | ❌ Linux |

## 📦 Wymagania

- **Java 11+** (JDK lub JRE)
- **Maven 3.6+** (tylko do budowania)

### Instalacja zależności (Ubuntu/Debian)

```bash
# Java
sudo apt-get update
sudo apt-get install openjdk-11-jdk

# Maven (tylko do budowania)
sudo apt-get install maven
```

## 🔨 Budowanie

```bash
cd java/emf-converter
chmod +x build.sh
./build.sh
```

Po udanym buildzie JAR będzie w: `target/emf-converter.jar`

### Ręczne budowanie (bez skryptu)

```bash
mvn clean package
```

## 🚀 Użycie

### Podstawowe użycie

```bash
java -jar emf-converter.jar input.emf output.svg
```

### Przykłady

```bash
# Konwersja pojedynczego pliku
java -jar emf-converter.jar logo.emf logo.svg

# Batch konwersja
for f in *.emf; do
    java -jar emf-converter.jar "$f" "${f%.emf}.svg"
done
```

## 🐍 Integracja z Pythonem

Konwerter jest używany przez DoclingForge do automatycznej konwersji obrazów EMF:

```python
import subprocess
import tempfile

def convert_emf_with_java(emf_data: bytes) -> str:
    """Konwertuje EMF do SVG używając Java."""
    with tempfile.NamedTemporaryFile(suffix='.emf', delete=False) as emf_file:
        emf_file.write(emf_data)
        emf_path = emf_file.name
    
    with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as svg_file:
        svg_path = svg_file.name
    
    try:
        result = subprocess.run(
            ['java', '-jar', 'java/emf-converter/target/emf-converter.jar', 
             emf_path, svg_path],
            capture_output=True,
            timeout=10
        )
        
        if result.returncode == 0:
            with open(svg_path, 'r') as f:
                return f.read()
    finally:
        os.unlink(emf_path)
        os.unlink(svg_path)
    
    return None
```

## 📊 Wydajność

- **Startup time**: ~200-500ms (JVM startup)
- **Conversion time**: 50-200ms na obraz (zależy od złożoności)
- **Memory**: ~50-100MB (JVM heap)

### Optymalizacja

Dla wielu konwersji możesz zmniejszyć heap JVM:

```bash
java -Xmx128m -jar emf-converter.jar input.emf output.svg
```

## 🔧 Rozwiązywanie problemów

### "Error: Could not find or load main class"

Upewnij się, że używasz JAR z `target/emf-converter.jar` (z zależnościami).

### "UnsupportedClassVersionError"

Twoja Java jest za stara. Projekt wymaga Java 11+:

```bash
java -version  # Sprawdź wersję
sudo apt-get install openjdk-11-jdk
```

### Plik SVG jest pusty

EMF może być uszkodzony lub w nieobsługiwanym formacie. Sprawdź stderr:

```bash
java -jar emf-converter.jar input.emf output.svg 2>&1 | tee log.txt
```

## 📚 Biblioteki

Projekt używa:

- **freehep-graphicsio-emf** (2.4) - Parser EMF
- **freehep-graphicsio-svg** (2.4) - Generator SVG
- **freehep-graphics2d** (2.4) - Graphics2D API

Licencja: LGPL 2.1

## 🔄 Rozwój

### Dodawanie nowych funkcji

1. Edytuj `src/main/java/com/doclingforge/emfconverter/EmfConverter.java`
2. Przebuduj: `./build.sh`
3. Testuj: `java -jar target/emf-converter.jar test.emf test.svg`

### Dodawanie testów

Utwórz testy w `src/test/java/`:

```java
import org.junit.Test;
import static org.junit.Assert.*;

public class EmfConverterTest {
    @Test
    public void testConversion() throws Exception {
        // Your test here
    }
}
```

Uruchom testy:

```bash
mvn test
```

## 📄 Licencja

Część projektu DoclingForge.
FreeHEP libraries są na licencji LGPL 2.1.

