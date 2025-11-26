package com.doclingforge.emfconverter;

import com.doclingforge.emfconverter.emfplus.EmfPlusParser;
import org.freehep.graphicsio.emf.EMFInputStream;
import org.freehep.graphicsio.emf.EMFRenderer;
import org.freehep.graphicsio.svg.SVGGraphics2D;
import org.apache.poi.hwmf.draw.HwmfGraphics;
import org.apache.poi.hwmf.record.HwmfEscape;
import org.apache.poi.hwmf.record.HwmfPlaceableHeader;
import org.apache.poi.hwmf.record.HwmfRecord;
import org.apache.poi.hwmf.usermodel.HwmfPicture;

import java.awt.*;
import java.awt.geom.AffineTransform;
import java.awt.geom.Dimension2D;
import java.awt.geom.Rectangle2D;
import java.awt.image.BufferedImage;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.Base64;

import javax.imageio.ImageIO;

/**
 * Konwerter EMF/WMF do SVG używający FreeHEP VectorGraphics.
 * 
 * FreeHEP oferuje lepsze wsparcie dla EMF niż Apache Batik.
 * 
 * Użycie:
 *   java -jar emf-converter.jar input.emf output.svg
 */
public class EmfConverter {

    private static final Logger LOGGER = Logger.getLogger(EmfConverter.class.getName());
    
    public static void main(String[] args) {
        if (args.length != 2) {
            System.err.println("Usage: java -jar emf-converter.jar <input.emf> <output.svg>");
            System.exit(1);
        }
        
        String inputPath = args[0];
        String outputPath = args[1];
        
        try {
            convertEmfToSvg(inputPath, outputPath);
            System.out.println("Conversion successful: " + inputPath + " -> " + outputPath);
            System.exit(0);
        } catch (Exception e) {
            System.err.println("Error converting EMF to SVG: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        }
    }
    
    /**
     * Konwertuje plik EMF/WMF na SVG.
     * 
     * @param inputPath Ścieżka do pliku wejściowego EMF/WMF
     * @param outputPath Ścieżka do pliku wyjściowego SVG
     * @throws Exception Jeśli konwersja się nie powiedzie
     */
    public static void convertEmfToSvg(String inputPath, String outputPath) throws Exception {
        // Sprawdź czy plik wejściowy istnieje
        File inputFile = new File(inputPath);
        if (!inputFile.exists()) {
            throw new FileNotFoundException("Input file not found: " + inputPath);
        }
        
        // Sprawdź rozszerzenie pliku
        String fileName = inputFile.getName().toLowerCase();
        boolean isEmf = fileName.endsWith(".emf");
        boolean isWmf = fileName.endsWith(".wmf");
        
        if (!isEmf && !isWmf) {
            throw new IllegalArgumentException("Input file must be EMF or WMF format");
        }
        
        // Przeczytaj dane i przekonwertuj
        if (isEmf) {
            byte[] emfBytes = Files.readAllBytes(inputFile.toPath());
            Dimension2D size;
            try (EMFInputStream headerStream = new EMFInputStream(new ByteArrayInputStream(emfBytes))) {
                size = headerStream.readHeader().getBounds().getSize();
            }

            int width = (int) Math.ceil(size.getWidth());
            int height = (int) Math.ceil(size.getHeight());
            if (width <= 0 || width > 20000) width = 800;
            if (height <= 0 || height > 20000) height = 600;

            try (FileOutputStream fos = new FileOutputStream(outputPath)) {
                SVGGraphics2D svgGraphics = new SVGGraphics2D(fos, new Dimension(width, height));
                svgGraphics.startExport();

                boolean renderedGdi = false;
                try (EMFInputStream emfStream = new EMFInputStream(new ByteArrayInputStream(emfBytes))) {
                    EMFRenderer renderer = new EMFRenderer(emfStream);
                    renderer.paint(svgGraphics);
                    renderedGdi = true;
                } catch (Exception ex) {
                    LOGGER.log(Level.FINE, "FreeHEP EMF renderer failed, will rely on EMF+ parser", ex);
                }

                EmfPlusParser emfPlusParser = new EmfPlusParser(emfBytes, svgGraphics);
                emfPlusParser.parse();

                svgGraphics.endExport();

                if (!renderedGdi && !emfPlusParser.hasDetectedRecords()) {
                    LOGGER.warning("EMF rendering failed and no EMF+ records detected; output may be empty.");
                }
            }
        } else {
            byte[] wmfBytes = Files.readAllBytes(inputFile.toPath());
            HwmfPicture picture;
            try (ByteArrayInputStream bais = new ByteArrayInputStream(wmfBytes)) {
                picture = new HwmfPicture(bais);
            }

            byte[] embeddedEmf = extractEmbeddedEmf(picture);
            if (embeddedEmf != null && embeddedEmf.length > 0) {
                String svg = convertEmfBytesToSvg(embeddedEmf);
                try (FileOutputStream fos = new FileOutputStream(outputPath)) {
                    fos.write(svg.getBytes(StandardCharsets.UTF_8));
                }
                return;
            }

            Dimension2D size = resolveWmfSize(picture);
            int width = normalizeDimension(size.getWidth());
            int height = normalizeDimension(size.getHeight());
            String svgContent = renderWmfToEmbeddedSvg(picture, width, height);
            try (FileOutputStream fos = new FileOutputStream(outputPath)) {
                fos.write(svgContent.getBytes(StandardCharsets.UTF_8));
            }
        }
        
        // Sprawdź czy plik został utworzony
        File outputFile = new File(outputPath);
        if (!outputFile.exists() || outputFile.length() == 0) {
            throw new IOException("Output SVG file was not created or is empty");
        }
    }
    
    /**
     * Konwertuje dane EMF/WMF z bajtów na string SVG.
     * 
     * @param emfData Dane EMF/WMF jako tablica bajtów
     * @return String zawierający SVG
     * @throws Exception Jeśli konwersja się nie powiedzie
     */
    public static String convertEmfBytesToSvg(byte[] emfData) throws Exception {
        boolean isEmf = emfData.length >= 4 && emfData[0] == 0x01 && emfData[1] == 0x00 && emfData[2] == 0x00 && emfData[3] == 0x00;
        boolean isWmf = emfData.length >= 2 && (emfData[0] & 0xFF) == 0xD7 && (emfData[1] & 0xFF) == 0xCD;

        if (!isEmf && !isWmf) {
            throw new IllegalArgumentException("Input must be EMF or WMF data");
        }

        ByteArrayOutputStream baos = new ByteArrayOutputStream();

        if (isEmf) {
            byte[] emfCopy = emfData.clone();
            try (EMFInputStream emfHeader = new EMFInputStream(new ByteArrayInputStream(emfCopy))) {
                Dimension2D size = emfHeader.readHeader().getBounds().getSize();

                int width = (int) Math.ceil(size.getWidth());
                int height = (int) Math.ceil(size.getHeight());
                if (width <= 0 || width > 20000) width = 800;
                if (height <= 0 || height > 20000) height = 600;

                try (EMFInputStream emfStream = new EMFInputStream(new ByteArrayInputStream(emfCopy))) {
                    SVGGraphics2D svgGraphics = new SVGGraphics2D(baos, new Dimension(width, height));
                    svgGraphics.startExport();

                    EMFRenderer renderer = new EMFRenderer(emfStream);
                    renderer.paint(svgGraphics);

                    EmfPlusParser emfPlusParser = new EmfPlusParser(emfCopy, svgGraphics);
                    emfPlusParser.parse();

                    svgGraphics.endExport();
                }
            }
        } else {
            byte[] wmfCopy = emfData.clone();
            HwmfPicture picture;
            try (ByteArrayInputStream bais = new ByteArrayInputStream(wmfCopy)) {
                picture = new HwmfPicture(bais);
            }

        byte[] embeddedEmf = extractEmbeddedEmf(picture);
        if (embeddedEmf != null && embeddedEmf.length > 0) {
            return convertEmfBytesToSvg(embeddedEmf);
        }

            Dimension2D size = resolveWmfSize(picture);
            int width = normalizeDimension(size.getWidth());
            int height = normalizeDimension(size.getHeight());
            return renderWmfToEmbeddedSvg(picture, width, height);
        }

        return baos.toString("UTF-8");
    }

    private static Dimension2D resolveWmfSize(HwmfPicture picture) {
        Dimension2D size = null;
        try {
            size = picture.getSize();
        } catch (IllegalStateException ignored) {
            // Fallback to other heuristics
        }

        if (size == null || size.getWidth() <= 0 || size.getHeight() <= 0) {
            try {
                Rectangle bounds = picture.getBounds().getBounds();
                if (bounds.getWidth() > 0 && bounds.getHeight() > 0) {
                    size = new Dimension(bounds.width, bounds.height);
                }
            } catch (IllegalStateException ignored) {
                // Window origin/extent may be missing, continue to placeable header
            }
        }

        if ((size == null || size.getWidth() <= 0 || size.getHeight() <= 0) && picture.getPlaceableHeader() != null) {
            HwmfPlaceableHeader placeable = picture.getPlaceableHeader();
            Rectangle2D bounds = placeable.getBounds();
            int unitsPerInch = placeable.getUnitsPerInch();
            if (bounds != null && bounds.getWidth() > 0 && bounds.getHeight() > 0 && unitsPerInch > 0) {
                double widthPt = bounds.getWidth() * 72.0 / unitsPerInch;
                double heightPt = bounds.getHeight() * 72.0 / unitsPerInch;
                size = new Dimension((int) Math.ceil(Math.max(widthPt, 1d)), (int) Math.ceil(Math.max(heightPt, 1d)));
            }
        }

        if (size == null || size.getWidth() <= 0 || size.getHeight() <= 0) {
            size = new Dimension(800, 600);
        }

        return size;
    }

    private static void applyPlaceableTransform(HwmfGraphics graphics, HwmfPicture picture) {
        HwmfPlaceableHeader placeable = picture.getPlaceableHeader();
        if (placeable == null) {
            return;
        }
        Rectangle2D rawBounds = placeable.getBounds();
        int unitsPerInch = placeable.getUnitsPerInch();
        if (rawBounds == null || unitsPerInch <= 0) {
            return;
        }
        double scale = 72.0 / unitsPerInch;
        AffineTransform transform = graphics.getInitTransform();
        transform.translate(-rawBounds.getX(), -rawBounds.getY());
        transform.scale(scale, scale);
        graphics.setTransform(transform);
    }

    private static byte[] extractEmbeddedEmf(HwmfPicture picture) {
        for (HwmfRecord record : picture.getRecords()) {
            if (record instanceof HwmfEscape) {
                HwmfEscape escape = (HwmfEscape) record;
                if (escape.getEscapeFunction() == HwmfEscape.EscapeFunction.META_ESCAPE_ENHANCED_METAFILE) {
                    HwmfEscape.HwmfEscapeData data = escape.getEscapeData();
                    if (data instanceof HwmfEscape.WmfEscapeEMF) {
                        HwmfEscape.WmfEscapeEMF emf = (HwmfEscape.WmfEscapeEMF) data;
                        if (emf.getEmfData() != null && emf.getEmfData().length > 0) {
                            return emf.getEmfData();
                        }
                    }
                }
            }
        }
        return null;
    }

    private static int normalizeDimension(double value) {
        if (Double.isFinite(value) && value > 0 && value < 20000) {
            return (int) Math.ceil(value);
        }
        return 800;
    }

    private static String renderWmfToEmbeddedSvg(HwmfPicture picture, int width, int height) throws IOException {
        BufferedImage image = new BufferedImage(Math.max(width, 1), Math.max(height, 1), BufferedImage.TYPE_INT_ARGB);
        Graphics2D g2d = image.createGraphics();
        g2d.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        try {
            picture.draw(g2d, new Rectangle2D.Double(0, 0, width, height));
        } catch (IllegalStateException ex) {
            HwmfGraphics graphics = new HwmfGraphics(g2d, new Rectangle2D.Double(0, 0, width, height));
            applyPlaceableTransform(graphics, picture);
            graphics.getProperties().setWindowOrg(0, 0);
            graphics.getProperties().setWindowExt(width, height);
            graphics.getProperties().setViewportExt(width, height);
            picture.forEach(record -> record.draw(graphics));
        }
        g2d.dispose();

        ByteArrayOutputStream pngBuffer = new ByteArrayOutputStream();
        ImageIO.write(image, "PNG", pngBuffer);
        String base64 = Base64.getEncoder().encodeToString(pngBuffer.toByteArray());

        return "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
                + "<svg xmlns=\"http://www.w3.org/2000/svg\" xmlns:xlink=\"http://www.w3.org/1999/xlink\" "
                + "width=\"" + width + "\" height=\"" + height + "\" viewBox=\"0 0 " + width + " " + height + "\">\n"
                + "  <image x=\"0\" y=\"0\" width=\"" + width + "\" height=\"" + height + "\" xlink:href=\"data:image/png;base64,"
                + base64 + "\"/>\n"
                + "</svg>\n";
    }
}

