package com.doclingforge.emfconverter.emfplus;

import org.freehep.graphicsio.svg.SVGGraphics2D;

import java.awt.AlphaComposite;
import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Composite;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.LinearGradientPaint;
import java.awt.MultipleGradientPaint;
import java.awt.Paint;
import java.awt.RadialGradientPaint;
import java.awt.Shape;
import java.awt.Stroke;
import java.awt.font.FontRenderContext;
import java.awt.font.GlyphVector;
import java.awt.image.BufferedImage;
import java.awt.image.RasterFormatException;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.awt.geom.AffineTransform;
import java.awt.geom.Area;
import java.awt.geom.GeneralPath;
import java.awt.geom.Point2D;
import java.awt.geom.Rectangle2D;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Deque;
import java.util.EnumMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import javax.imageio.ImageIO;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Lightweight EMF+ parser that identifies EMF+ comment streams embedded inside EMF files and renders
 * the high-impact records we support directly onto the provided {@link SVGGraphics2D} instance.
 *
 * This class currently focuses on the primitives most frequently encountered in Office-generated EMF+ streams:
 * brush creation, rectangle fills, and basic world-transform manipulation. The infrastructure is extensible so we
 * can progressively implement additional record types (paths, strings, images, etc.) without reworking the parser.
 */
public class EmfPlusParser {

    private static final Logger LOGGER = Logger.getLogger(EmfPlusParser.class.getName());

    private static final int EMR_COMMENT = 70;
    private static final int EMFPLUS_SIGNATURE = 0x2B464D45; // 'EMF+'
    private static final int EMFPLUS_FLAG_HAS_RECORDS = 0x00000001;

    private static final int OBJECT_TABLE_SIZE = 256;

    private static final int BRUSH_TYPE_SOLID_COLOR = 0;
    private static final int BRUSH_TYPE_HATCH = 1;
    private static final int BRUSH_TYPE_TEXTURE = 2;
    private static final int BRUSH_TYPE_PATH_GRADIENT = 3;
    private static final int BRUSH_TYPE_LINEAR_GRADIENT = 4;
    private static final int IMAGE_TYPE_BITMAP = 1;
    private static final int BITMAP_DATA_TYPE_PIXEL = 0;
    private static final int BITMAP_DATA_TYPE_COMPRESSED = 1;
    private static final int PIXEL_FORMAT_INDEXED_FLAG = 0x00010000;
    private static final int PIXEL_FORMAT_32BPP_ARGB = 0x0026200A;
    private static final int PIXEL_FORMAT_32BPP_PARGB = 0x000E200B;
    private static final int PIXEL_FORMAT_32BPP_RGB = 0x00022009;
    private static final int PIXEL_FORMAT_24BPP_RGB = 0x00021808;
    private static final int PIXEL_FORMAT_8BPP_INDEXED = 0x00030803;
    private static final int STRING_ALIGNMENT_NEAR = 0;
    private static final int STRING_ALIGNMENT_CENTER = 1;
    private static final int STRING_ALIGNMENT_FAR = 2;
    private static final int STRING_FORMAT_FLAG_NO_WRAP = 0x00001000;
    private static final int REGION_DATA_RECT = 0x10000000;
    private static final int REGION_DATA_PATH = 0x10000001;
    private static final int REGION_DATA_EMPTY_RECT = 0x10000002;
    private static final int REGION_DATA_INFINITE_RECT = 0x10000003;
    private static final int BRUSH_DATA_PATH = 1 << 0;
    private static final int BRUSH_DATA_TRANSFORM = 1 << 1;
    private static final int BRUSH_DATA_PRESET_COLORS = 1 << 2;
    private static final int BRUSH_DATA_BLEND_FACTORS_H = 1 << 3;
    private static final int BRUSH_DATA_BLEND_FACTORS_V = 1 << 4;
    private static final int BRUSH_DATA_FOCUS_SCALES = 1 << 6;
    private static final int BRUSH_DATA_GAMMA = 1 << 7;
    private static final int BRUSH_DATA_DO_NOT_TRANSFORM = 1 << 8;
    private static final int DRIVER_STRING_OPTION_CMAP_LOOKUP = 0x0001;
    private static final int DRIVER_STRING_OPTION_VERTICAL = 0x0002;
    private static final int DRIVER_STRING_OPTION_REALIZED_ADVANCE = 0x0004;
    private static final int DRIVER_STRING_OPTION_LIMIT_SUBPIXEL = 0x0008;

    private final byte[] emfData;
    private final SVGGraphics2D graphics;

    private boolean detectedRecords = false;
    private final EnumMap<EmfPlusRecordType, Integer> recordHistogram = new EnumMap<>(EmfPlusRecordType.class);

    private final Paint[] brushTable = new Paint[OBJECT_TABLE_SIZE];
    private final PenInfo[] penTable = new PenInfo[OBJECT_TABLE_SIZE];
    private final GeneralPath[] pathTable = new GeneralPath[OBJECT_TABLE_SIZE];
    private final BufferedImage[] imageTable = new BufferedImage[OBJECT_TABLE_SIZE];
    private final Font[] fontTable = new Font[OBJECT_TABLE_SIZE];
    private final ImageAttributesInfo[] imageAttributesTable = new ImageAttributesInfo[OBJECT_TABLE_SIZE];
    private final StringFormatInfo[] stringFormatTable = new StringFormatInfo[OBJECT_TABLE_SIZE];
    private final Area[] regionTable = new Area[OBJECT_TABLE_SIZE];
    private final Deque<GraphicsState> stateStack = new ArrayDeque<>();

    private AffineTransform baseTransform;
    private AffineTransform worldTransform;

    public EmfPlusParser(byte[] emfData, SVGGraphics2D graphics) {
        this.emfData = emfData;
        this.graphics = graphics;
    }

    public boolean hasDetectedRecords() {
        return detectedRecords;
    }

    public Map<EmfPlusRecordType, Integer> getRecordHistogram() {
        return Collections.unmodifiableMap(recordHistogram);
    }

    /**
     * Scan EMF records for EMF+ comment blocks. For each EMF+ record encountered we either render it (if supported)
     * or record its presence for diagnostic purposes.
     */
    public void parse() {
        if (emfData == null || emfData.length < 16 || graphics == null) {
            return;
        }

        final AffineTransform initialTransform = graphics.getTransform();
        resetState(initialTransform);

        try {
            ByteBuffer buffer = ByteBuffer.wrap(emfData).order(ByteOrder.LITTLE_ENDIAN);
            while (buffer.remaining() >= 8) {
                int recordType = buffer.getInt();
                int recordSize = buffer.getInt();
                if (recordSize < 8 || recordSize - 8 > buffer.remaining()) {
                    LOGGER.warning("Malformed EMF record encountered while scanning for EMF+ comments.");
                    break;
                }
                int dataSize = recordSize - 8;
                byte[] recordData = new byte[dataSize];
                buffer.get(recordData);

                if (recordType == EMR_COMMENT) {
                    parseComment(recordData);
                }
            }
        } finally {
            graphics.setTransform(initialTransform);
        }
    }

    private MultipleGradientPaint.CycleMethod cycleMethodFromWrapMode(int wrapMode) {
        switch (wrapMode) {
            case 0: // Tile
                return MultipleGradientPaint.CycleMethod.REPEAT;
            case 1: // TileFlipX
            case 2: // TileFlipY
            case 3: // TileFlipXY
                return MultipleGradientPaint.CycleMethod.REFLECT;
            case 4: // Clamp
            default:
                return MultipleGradientPaint.CycleMethod.NO_CYCLE;
        }
    }

    private float clamp01(float value) {
        if (Float.isNaN(value)) {
            return 0f;
        }
        if (value < 0f) {
            return 0f;
        }
        if (value > 1f) {
            return 1f;
        }
        return value;
    }

    private Color interpolateColor(Color start, Color end, float t) {
        t = clamp01(t);
        int a = (int) Math.round(start.getAlpha() + (end.getAlpha() - start.getAlpha()) * t);
        int r = (int) Math.round(start.getRed() + (end.getRed() - start.getRed()) * t);
        int g = (int) Math.round(start.getGreen() + (end.getGreen() - start.getGreen()) * t);
        int b = (int) Math.round(start.getBlue() + (end.getBlue() - start.getBlue()) * t);
        return new Color(
                clampToRange(a, 0, 255),
                clampToRange(r, 0, 255),
                clampToRange(g, 0, 255),
                clampToRange(b, 0, 255)
        );
    }

    private void sortGradientStops(float[] fractions, Color[] colors) {
        if (fractions.length <= 1) {
            return;
        }
        List<Integer> indices = new ArrayList<>(fractions.length);
        for (int i = 0; i < fractions.length; i++) {
            indices.add(i);
        }
        indices.sort((a, b) -> Float.compare(fractions[a], fractions[b]));
        float[] sortedFractions = new float[fractions.length];
        Color[] sortedColors = new Color[colors.length];
        for (int i = 0; i < indices.size(); i++) {
            int idx = indices.get(i);
            sortedFractions[i] = fractions[idx];
            sortedColors[i] = colors[idx];
        }
        System.arraycopy(sortedFractions, 0, fractions, 0, fractions.length);
        System.arraycopy(sortedColors, 0, colors, 0, colors.length);
    }

    private GradientStops dedupeGradientStops(float[] fractions, Color[] colors) {
        if (fractions.length <= 1) {
            return new GradientStops(fractions, colors);
        }
        List<Float> fractionList = new ArrayList<>(fractions.length);
        List<Color> colorList = new ArrayList<>(colors.length);
        float previous = Float.NaN;
        for (int i = 0; i < fractions.length; i++) {
            float fraction = fractions[i];
            Color color = colors[i];
            if (!fractionList.isEmpty() && Math.abs(previous - fraction) < 1e-6f) {
                // Overwrite the last color to keep the most recent definition.
                colorList.set(colorList.size() - 1, color);
            } else {
                fractionList.add(fraction);
                colorList.add(color);
                previous = fraction;
            }
        }
        float[] dedupedFractions = new float[fractionList.size()];
        Color[] dedupedColors = new Color[colorList.size()];
        for (int i = 0; i < fractionList.size(); i++) {
            dedupedFractions[i] = fractionList.get(i);
            dedupedColors[i] = colorList.get(i);
        }
        return new GradientStops(dedupedFractions, dedupedColors);
    }

    private GradientStops ensureBoundaryStops(float[] fractions, Color[] colors) {
        if (fractions.length == 0) {
            return new GradientStops(fractions, colors);
        }
        boolean hasZero = Math.abs(fractions[0]) < 1e-6f;
        boolean hasOne = Math.abs(fractions[fractions.length - 1] - 1f) < 1e-6f;
        if (hasZero && hasOne) {
            return new GradientStops(fractions, colors);
        }
        int newSize = fractions.length + (hasZero ? 0 : 1) + (hasOne ? 0 : 1);
        float[] expandedFractions = new float[newSize];
        Color[] expandedColors = new Color[newSize];
        int index = 0;
        if (!hasZero) {
            expandedFractions[index] = 0f;
            expandedColors[index] = colors[0];
            index++;
        }
        System.arraycopy(fractions, 0, expandedFractions, index, fractions.length);
        System.arraycopy(colors, 0, expandedColors, index, colors.length);
        index += fractions.length;
        if (!hasOne) {
            expandedFractions[index] = 1f;
            expandedColors[index] = colors[colors.length - 1];
        }
        return new GradientStops(expandedFractions, expandedColors);
    }

    private float convertFontSize(float emSize, int unit) {
        switch (unit) {
            case 2: // Pixel
                return emSize * (72f / 96f);
            case 3: // Point
                return emSize;
            case 4: // Inch
                return emSize * 72f;
            case 5: // Document (1/300 inch)
                return emSize * (72f / 300f);
            case 6: // Millimeter
                return emSize * (72f / 25.4f);
            default:
                return emSize;
        }
    }

    private Paint createPathGradientFallback(Color centerColor, Color[] surroundingColors, int wrapMode) {
        Color outerColor = surroundingColors != null && surroundingColors.length > 0
                ? averageColors(surroundingColors)
                : centerColor;
        if (outerColor == null) {
            outerColor = centerColor;
        }
        if (!outerColor.equals(centerColor)) {
            Color finalOuterColor = outerColor;
            LOGGER.fine(() -> "Path gradient degraded to averaged boundary color (" + colorToHex(finalOuterColor)
                    + "), wrapMode=" + wrapMode);
        } else {
            LOGGER.fine(() -> "Path gradient fell back to center color, wrapMode=" + wrapMode);
        }
        return outerColor;
    }

    private GradientStops readPathGradientPresetStops(ByteBuffer buffer) {
        if (buffer.remaining() < Integer.BYTES) {
            LOGGER.fine("Path gradient preset stop count missing.");
            return null;
        }
        int count = buffer.getInt();
        if (count <= 0 || count > 4096) {
            LOGGER.fine("Path gradient preset stop count invalid: " + count);
            return null;
        }
        int required = count * (Float.BYTES + Integer.BYTES);
        if (buffer.remaining() < required) {
            LOGGER.fine("Path gradient preset stop data truncated.");
            return null;
        }
        float[] fractions = new float[count];
        Color[] colors = new Color[count];
        for (int i = 0; i < count; i++) {
            fractions[i] = clamp01(buffer.getFloat());
        }
        for (int i = 0; i < count; i++) {
            colors[i] = new Color(buffer.getInt(), true);
        }
        return new GradientStops(fractions, colors);
    }

    private GradientBlend readPathGradientBlend(ByteBuffer buffer) {
        if (buffer.remaining() < Integer.BYTES) {
            LOGGER.fine("Path gradient blend entry count missing.");
            return null;
        }
        int count = buffer.getInt();
        if (count <= 0 || count > 4096) {
            LOGGER.fine("Path gradient blend entry count invalid: " + count);
            return null;
        }
        int required = count * Float.BYTES * 2;
        if (buffer.remaining() < required) {
            LOGGER.fine("Path gradient blend data truncated.");
            return null;
        }
        float[] fractions = new float[count];
        float[] factors = new float[count];
        for (int i = 0; i < count; i++) {
            fractions[i] = clamp01(buffer.getFloat());
        }
        for (int i = 0; i < count; i++) {
            factors[i] = clamp01(buffer.getFloat());
        }
        return new GradientBlend(fractions, factors);
    }

    private double normalizeFocusScale(double value) {
        if (Double.isNaN(value) || Double.isInfinite(value)) {
            return 1.0;
        }
        double magnitude = Math.abs(value);
        if (magnitude < 1e-3) {
            magnitude = 1e-3;
        }
        if (magnitude > 1000.0) {
            magnitude = 1000.0;
        }
        return magnitude;
    }

    private Color averageColors(Color[] colors) {
        if (colors == null || colors.length == 0) {
            return null;
        }
        long a = 0;
        long r = 0;
        long g = 0;
        long b = 0;
        for (Color color : colors) {
            a += color.getAlpha();
            r += color.getRed();
            g += color.getGreen();
            b += color.getBlue();
        }
        int count = colors.length;
        return new Color(
                clampToRange((int) Math.round((double) r / count), 0, 255),
                clampToRange((int) Math.round((double) g / count), 0, 255),
                clampToRange((int) Math.round((double) b / count), 0, 255),
                clampToRange((int) Math.round((double) a / count), 0, 255)
        );
    }

    private String colorToHex(Color color) {
        if (color == null) {
            return "#00000000";
        }
        return String.format("#%02X%02X%02X%02X",
                color.getAlpha(),
                color.getRed(),
                color.getGreen(),
                color.getBlue());
    }

    private AffineTransform readAffineTransform(ByteBuffer buffer) {
        double m11 = buffer.getFloat();
        double m12 = buffer.getFloat();
        double m21 = buffer.getFloat();
        double m22 = buffer.getFloat();
        double dx = buffer.getFloat();
        double dy = buffer.getFloat();
        return new AffineTransform(m11, m12, m21, m22, dx, dy);
    }

    private void resetState(AffineTransform initialTransform) {
        detectedRecords = false;
        recordHistogram.clear();
        Arrays.fill(brushTable, null);
        Arrays.fill(penTable, null);
        Arrays.fill(pathTable, null);
        Arrays.fill(imageTable, null);
        Arrays.fill(fontTable, null);
        Arrays.fill(imageAttributesTable, null);
        Arrays.fill(stringFormatTable, null);
        Arrays.fill(regionTable, null);
        stateStack.clear();

        baseTransform = new AffineTransform(initialTransform);
        worldTransform = new AffineTransform(initialTransform);
        graphics.setTransform(worldTransform);
    }

    private void parseComment(byte[] recordData) {
        if (recordData.length < 4) {
            return;
        }
        ByteBuffer comment = ByteBuffer.wrap(recordData).order(ByteOrder.LITTLE_ENDIAN);
        int byteCount = comment.getInt();
        if (byteCount <= 0 || byteCount > comment.remaining()) {
            byteCount = Math.min(comment.remaining(), Math.max(byteCount, 0));
        }
        byte[] payload = new byte[byteCount];
        comment.get(payload, 0, payload.length);

        ByteBuffer payloadBuffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        if (payloadBuffer.remaining() < 16) {
            return;
        }
        int signature = payloadBuffer.getInt();
        if (signature != EMFPLUS_SIGNATURE) {
            return;
        }

        int version = payloadBuffer.getInt();
        int flags = payloadBuffer.getInt();
        int dataSize = payloadBuffer.getInt();
        if ((flags & EMFPLUS_FLAG_HAS_RECORDS) == 0) {
            LOGGER.fine(() -> "EMF+ comment without record payload (flags=" + Integer.toHexString(flags) + ")");
            return;
        }
        if (dataSize <= 0 || dataSize > payloadBuffer.remaining()) {
            dataSize = Math.min(payloadBuffer.remaining(), Math.max(dataSize, 0));
        }

        byte[] recordBytes = new byte[dataSize];
        payloadBuffer.get(recordBytes, 0, recordBytes.length);
        parseRecords(ByteBuffer.wrap(recordBytes).order(ByteOrder.LITTLE_ENDIAN), version);
    }

    private void parseRecords(ByteBuffer buffer, int version) {
        while (buffer.remaining() >= 12) {
            int type = buffer.getShort() & 0xFFFF;
            int flags = buffer.getShort() & 0xFFFF;
            int sizeUnits = buffer.getInt();
            int dataSizeUnits = buffer.getInt();

            int sizeBytes = sizeUnits * 4;
            int dataSizeBytes = dataSizeUnits * 4;
            int payloadLength = Math.max(sizeBytes - 12, 0);

            if (payloadLength > buffer.remaining()) {
                LOGGER.warning("EMF+ record truncated (type=" + type + ", sizeUnits=" + sizeUnits + ")");
                break;
            }

            byte[] payload = new byte[payloadLength];
            buffer.get(payload, 0, payload.length);

            EmfPlusRecordType recordType = EmfPlusRecordType.fromCode(type);
            detectedRecords = true;
            recordHistogram.merge(recordType, 1, Integer::sum);

            handleRecord(recordType, flags, payload, dataSizeBytes, version);
        }

        if (!recordHistogram.isEmpty()) {
            LOGGER.log(Level.INFO, () -> "EMF+ records detected: " + recordHistogram);
        }
    }

    private void handleRecord(
            EmfPlusRecordType recordType,
            int flags,
            byte[] payload,
            int dataSize,
            int version
    ) {
        if (recordType == EmfPlusRecordType.UNKNOWN || recordType == EmfPlusRecordType.INVALID) {
            LOGGER.fine(() -> "Encountered unknown EMF+ record type code.");
            return;
        }

        LOGGER.log(
                Level.FINER,
                () -> "EMF+ record " + recordType + " flags=0x"
                        + Integer.toHexString(flags) + " payload=" + payload.length + " bytes"
        );

        switch (recordType) {
            case OBJECT:
                handleObject(flags, payload);
                break;
            case FILL_RECTS:
                handleFillRects(flags, payload);
                break;
            case SET_WORLD_TRANSFORM:
                handleSetWorldTransform(payload);
                break;
            case RESET_WORLD_TRANSFORM:
                resetWorldTransform();
                break;
            case TRANSLATE_WORLD_TRANSFORM:
                handleTranslateWorldTransform(flags, payload);
                break;
            case SCALE_WORLD_TRANSFORM:
                handleScaleWorldTransform(flags, payload);
                break;
            case ROTATE_WORLD_TRANSFORM:
                handleRotateWorldTransform(flags, payload);
                break;
            case MULTIPLY_WORLD_TRANSFORM:
                handleMultiplyWorldTransform(flags, payload);
                break;
            case SAVE:
                handleSave(payload);
                break;
            case RESTORE:
                handleRestore(payload);
                break;
            case FILL_PATH:
                handleFillPath(flags, payload);
                break;
            case DRAW_PATH:
                handleDrawPath(flags, payload);
                break;
            case RESET_CLIP:
                resetClip();
                break;
            case SET_CLIP_RECT:
                handleSetClipRect(flags, payload);
                break;
            case SET_CLIP_PATH:
                handleSetClipPath(flags, payload);
                break;
            case SET_CLIP_REGION:
                handleSetClipRegion(flags, payload);
                break;
            case DRAW_RECTS:
                handleDrawRects(flags, payload);
                break;
            case DRAW_IMAGE:
                handleDrawImage(flags, payload);
                break;
            case DRAW_STRING:
                handleDrawString(flags, payload);
                break;
            case DRAW_DRIVER_STRING:
                handleDrawDriverString(flags, payload);
                break;
            default:
                // Not yet implemented. We keep logging at FINE level for telemetry.
                break;
        }
    }

    private void handleObject(int flags, byte[] payload) {
        int objectId = flags & 0xFF;
        int objectTypeCode = (flags >>> 8) & 0xFF;
        EmfPlusObjectType objectType = EmfPlusObjectType.fromCode(objectTypeCode);

        switch (objectType) {
            case BRUSH:
                handleBrushObject(objectId, payload);
                break;
            case PEN:
                handlePenObject(objectId, payload);
                break;
            case PATH:
                handlePathObject(objectId, payload);
                break;
            case IMAGE:
                handleImageObject(objectId, payload);
                break;
            case IMAGE_ATTRIBUTES:
                handleImageAttributesObject(objectId, payload);
                break;
            case STRING_FORMAT:
                handleStringFormatObject(objectId, payload);
                break;
            case FONT:
                handleFontObject(objectId, payload);
                break;
            case REGION:
                handleRegionObject(objectId, payload);
                break;
            default:
                if (objectId < OBJECT_TABLE_SIZE) {
                    brushTable[objectId] = null;
                    penTable[objectId] = null;
                    pathTable[objectId] = null;
                    imageTable[objectId] = null;
                    imageAttributesTable[objectId] = null;
                    stringFormatTable[objectId] = null;
                    regionTable[objectId] = null;
                }
                LOGGER.fine(() -> "EMF+ object type " + objectType + " not yet supported.");
        }
    }

    private void handleBrushObject(int objectId, byte[] payload) {
        if (objectId < 0 || objectId >= OBJECT_TABLE_SIZE) {
            LOGGER.fine(() -> "Brush object id out of range: " + objectId);
            return;
        }
        Paint paint = parseBrushPayload(payload);
        brushTable[objectId] = paint;
    }

    private Paint resolveBrush(int brushId) {
        if (brushId < 0 || brushId >= OBJECT_TABLE_SIZE) {
            return null;
        }
        return brushTable[brushId];
    }

    private void handleFillRects(int flags, byte[] payload) {
        if (payload.length < 8) {
            LOGGER.fine("FillRects payload too small.");
            return;
        }

        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        int brushToken = buffer.getInt();
        int rectCount = buffer.getInt();

        if (rectCount <= 0) {
            return;
        }

        boolean rectanglesAreInteger = (flags & 0x4000) != 0;
        boolean brushFromColor = (flags & 0x8000) != 0;

        Paint paint = brushFromColor ? new Color(brushToken, true) : resolveBrush(brushToken);
        if (paint == null) {
            LOGGER.fine(() -> "FillRects missing brush for id=" + brushToken);
            return;
        }

        Paint originalPaint = graphics.getPaint();
        graphics.setPaint(paint);
        try {
            for (int i = 0; i < rectCount; i++) {
                double x;
                double y;
                double width;
                double height;

                if (rectanglesAreInteger) {
                    if (buffer.remaining() < 8) {
                        LOGGER.fine("FillRects integer payload truncated.");
                        return;
                    }
                    x = buffer.getShort();
                    y = buffer.getShort();
                    width = buffer.getShort();
                    height = buffer.getShort();
                } else {
                    if (buffer.remaining() < 16) {
                        LOGGER.fine("FillRects float payload truncated.");
                        return;
                    }
                    x = buffer.getFloat();
                    y = buffer.getFloat();
                    width = buffer.getFloat();
                    height = buffer.getFloat();
                }

                graphics.fill(new Rectangle2D.Double(x, y, width, height));
            }
        } finally {
            graphics.setPaint(originalPaint);
        }
    }

    private void handleSetWorldTransform(byte[] payload) {
        if (payload.length < 24) {
            LOGGER.fine("SetWorldTransform payload too small.");
            return;
        }
        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        double m11 = buffer.getFloat();
        double m12 = buffer.getFloat();
        double m21 = buffer.getFloat();
        double m22 = buffer.getFloat();
        double dx = buffer.getFloat();
        double dy = buffer.getFloat();

        worldTransform.setTransform(baseTransform);
        worldTransform.concatenate(new AffineTransform(m11, m12, m21, m22, dx, dy));
        graphics.setTransform(worldTransform);
    }

    private void handleTranslateWorldTransform(int flags, byte[] payload) {
        if (payload.length < 8) {
            LOGGER.fine("TranslateWorldTransform payload too small.");
            return;
        }
        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        double dx = buffer.getFloat();
        double dy = buffer.getFloat();
        applyDeltaTransform(AffineTransform.getTranslateInstance(dx, dy), decodeMatrixOrder(flags));
    }

    private void handleScaleWorldTransform(int flags, byte[] payload) {
        if (payload.length < 8) {
            LOGGER.fine("ScaleWorldTransform payload too small.");
            return;
        }
        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        double sx = buffer.getFloat();
        double sy = buffer.getFloat();
        applyDeltaTransform(AffineTransform.getScaleInstance(sx, sy), decodeMatrixOrder(flags));
    }

    private void handleRotateWorldTransform(int flags, byte[] payload) {
        if (payload.length < 4) {
            LOGGER.fine("RotateWorldTransform payload too small.");
            return;
        }
        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        double angleDegrees = buffer.getFloat();
        double angleRadians = Math.toRadians(angleDegrees);
        applyDeltaTransform(AffineTransform.getRotateInstance(angleRadians), decodeMatrixOrder(flags));
    }

    private void handleMultiplyWorldTransform(int flags, byte[] payload) {
        if (payload.length < 24) {
            LOGGER.fine("MultiplyWorldTransform payload too small.");
            return;
        }
        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        double m11 = buffer.getFloat();
        double m12 = buffer.getFloat();
        double m21 = buffer.getFloat();
        double m22 = buffer.getFloat();
        double dx = buffer.getFloat();
        double dy = buffer.getFloat();
        applyDeltaTransform(new AffineTransform(m11, m12, m21, m22, dx, dy), decodeMatrixOrder(flags));
    }

    private void handlePenObject(int objectId, byte[] payload) {
        if (objectId < 0 || objectId >= OBJECT_TABLE_SIZE) {
            LOGGER.fine(() -> "Pen object id out of range: " + objectId);
            return;
        }
        if (payload.length < 20) {
            LOGGER.fine("Pen object payload too small.");
            penTable[objectId] = null;
            return;
        }

        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        buffer.getInt(); // version
        buffer.getInt(); // type

        int penDataFlags = buffer.getInt();
        int penUnit = buffer.getInt();
        float penWidth = buffer.getFloat();

        if (penDataFlags != 0) {
            LOGGER.fine(() -> "Unsupported pen data flags: 0x" + Integer.toHexString(penDataFlags));
            penTable[objectId] = null;
            return;
        }

        // According to GDI+, 2 corresponds to UnitPixel. Other units require additional conversions.
        if (penUnit != 2) {
            LOGGER.fine(() -> "Unsupported pen unit: " + penUnit);
            penTable[objectId] = null;
            return;
        }

        byte[] brushBytes = new byte[buffer.remaining()];
        buffer.get(brushBytes);

        Paint paint = parseBrushPayload(brushBytes);
        if (paint == null) {
            penTable[objectId] = null;
            return;
        }

        float width = penWidth <= 0f ? 0.5f : penWidth;
        penTable[objectId] = new PenInfo(paint, width);
    }

    private void handlePathObject(int objectId, byte[] payload) {
        if (objectId < 0 || objectId >= OBJECT_TABLE_SIZE) {
            LOGGER.fine(() -> "Path object id out of range: " + objectId);
            return;
        }
        GeneralPath path = parsePathPayload(payload);
        pathTable[objectId] = path;
    }

    private void handleFillPath(int flags, byte[] payload) {
        int pathId = flags & 0xFF;
        GeneralPath path = resolvePath(pathId);
        if (path == null) {
            LOGGER.fine(() -> "FillPath missing path for id=" + pathId);
            return;
        }
        if (payload.length < 4) {
            LOGGER.fine("FillPath payload too small.");
            return;
        }
        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        int brushToken = buffer.getInt();
        boolean brushFromColor = (flags & 0x8000) != 0;
        Paint paint = brushFromColor ? new Color(brushToken, true) : resolveBrush(brushToken);
        if (paint == null) {
            LOGGER.fine(() -> "FillPath missing brush for id=" + brushToken);
            return;
        }

        Paint originalPaint = graphics.getPaint();
        graphics.setPaint(paint);
        try {
            graphics.fill(path);
        } finally {
            graphics.setPaint(originalPaint);
        }
    }

    private void handleDrawPath(int flags, byte[] payload) {
        int pathId = flags & 0xFF;
        GeneralPath path = resolvePath(pathId);
        if (path == null) {
            LOGGER.fine(() -> "DrawPath missing path for id=" + pathId);
            return;
        }
        if (payload.length < 4) {
            LOGGER.fine("DrawPath payload too small.");
            return;
        }
        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        int penId = buffer.getInt();
        PenInfo pen = resolvePen(penId);
        if (pen == null) {
            LOGGER.fine(() -> "DrawPath missing pen for id=" + penId);
            return;
        }

        Paint originalPaint = graphics.getPaint();
        Stroke originalStroke = graphics.getStroke();
        graphics.setPaint(pen.paint());
        graphics.setStroke(pen.stroke());
        try {
            graphics.draw(path);
        } finally {
            graphics.setPaint(originalPaint);
            graphics.setStroke(originalStroke);
        }
    }

    private void handleDrawRects(int flags, byte[] payload) {
        if (payload == null || payload.length < 4) {
            LOGGER.fine("DrawRects payload too small.");
            return;
        }

        int penId = flags & 0xFF;
        PenInfo pen = resolvePen(penId);
        if (pen == null) {
            LOGGER.fine(() -> "DrawRects missing pen for id=" + penId);
            return;
        }

        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        int rectCount = buffer.getInt();
        if (rectCount <= 0) {
            return;
        }

        boolean rectanglesAreInteger = (flags & 0x4000) != 0;
        Paint originalPaint = graphics.getPaint();
        Stroke originalStroke = graphics.getStroke();
        graphics.setPaint(pen.paint());
        graphics.setStroke(pen.stroke());

        try {
            for (int i = 0; i < rectCount; i++) {
                double x;
                double y;
                double width;
                double height;

                if (rectanglesAreInteger) {
                    if (buffer.remaining() < 8) {
                        LOGGER.fine("DrawRects integer payload truncated.");
                        return;
                    }
                    x = buffer.getShort();
                    y = buffer.getShort();
                    width = buffer.getShort();
                    height = buffer.getShort();
                } else {
                    if (buffer.remaining() < 16) {
                        LOGGER.fine("DrawRects float payload truncated.");
                        return;
                    }
                    x = buffer.getFloat();
                    y = buffer.getFloat();
                    width = buffer.getFloat();
                    height = buffer.getFloat();
                }

                graphics.draw(new Rectangle2D.Double(x, y, width, height));
            }
        } finally {
            graphics.setPaint(originalPaint);
            graphics.setStroke(originalStroke);
        }
    }

    private void handleImageObject(int objectId, byte[] payload) {
        if (objectId < 0 || objectId >= OBJECT_TABLE_SIZE) {
            LOGGER.fine(() -> "Image object id out of range: " + objectId);
            return;
        }
        if (payload == null || payload.length < 8) {
            LOGGER.fine("Image object payload too small.");
            imageTable[objectId] = null;
            return;
        }

        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        buffer.getInt(); // version
        int imageType = buffer.getInt();

        switch (imageType) {
            case IMAGE_TYPE_BITMAP:
                handleBitmapObject(objectId, buffer);
                break;
            default:
                LOGGER.fine(() -> "Unsupported EMF+ image type: " + imageType);
                imageTable[objectId] = null;
                break;
        }
    }

    private void handleBitmapObject(int objectId, ByteBuffer buffer) {
        if (buffer.remaining() < 20) {
            LOGGER.fine("Bitmap object payload too small.");
            imageTable[objectId] = null;
            return;
        }

        int width = buffer.getInt();
        int height = buffer.getInt();
        int stride = buffer.getInt();
        int pixelFormat = buffer.getInt();
        int bitmapType = buffer.getInt();

        byte[] remainingBytes = new byte[buffer.remaining()];
        buffer.get(remainingBytes);

        if (bitmapType == BITMAP_DATA_TYPE_COMPRESSED) {
            try (ByteArrayInputStream bais = new ByteArrayInputStream(remainingBytes)) {
                BufferedImage decoded = ImageIO.read(bais);
                if (decoded != null) {
                    imageTable[objectId] = decoded;
                } else {
                    LOGGER.fine("Failed to decode compressed bitmap image.");
                    imageTable[objectId] = null;
                }
            } catch (IOException ex) {
                LOGGER.log(Level.FINE, "Unable to decode compressed bitmap image.", ex);
                imageTable[objectId] = null;
            }
        } else if (bitmapType == BITMAP_DATA_TYPE_PIXEL) {
            ByteBuffer dataBuffer = ByteBuffer.wrap(remainingBytes).order(ByteOrder.LITTLE_ENDIAN);
            int[] palette = null;
            if ((pixelFormat & PIXEL_FORMAT_INDEXED_FLAG) != 0) {
                if (dataBuffer.remaining() < 8) {
                    LOGGER.fine("Indexed bitmap missing palette header.");
                    imageTable[objectId] = null;
                    return;
                }
                dataBuffer.getInt(); // palette flags (unused)
                int paletteCount = dataBuffer.getInt();
                if (paletteCount < 0 || paletteCount > 4096) {
                    LOGGER.fine(() -> "Indexed bitmap reported invalid palette count: " + paletteCount);
                    imageTable[objectId] = null;
                    return;
                }
                if (dataBuffer.remaining() < paletteCount * 4) {
                    LOGGER.fine("Indexed bitmap palette truncated.");
                    imageTable[objectId] = null;
                    return;
                }
                palette = new int[paletteCount];
                for (int i = 0; i < paletteCount; i++) {
                    palette[i] = dataBuffer.getInt();
                }
            }

            byte[] pixelData = new byte[dataBuffer.remaining()];
            dataBuffer.get(pixelData);

            BufferedImage bitmap = buildBitmapFromPixelData(width, height, stride, pixelFormat, pixelData, palette);
            if (bitmap != null) {
                imageTable[objectId] = bitmap;
            } else {
                LOGGER.fine(() -> "Failed to construct bitmap image (pixelFormat=0x"
                        + Integer.toHexString(pixelFormat) + ")");
                imageTable[objectId] = null;
            }
        } else {
            LOGGER.fine(() -> "Bitmap data type not supported: " + bitmapType);
            imageTable[objectId] = null;
        }
    }

    private void handleImageAttributesObject(int objectId, byte[] payload) {
        if (objectId < 0 || objectId >= OBJECT_TABLE_SIZE) {
            LOGGER.fine(() -> "Image attributes object id out of range: " + objectId);
            return;
        }
        if (payload == null || payload.length < 24) {
            LOGGER.fine("Image attributes payload too small.");
            imageAttributesTable[objectId] = null;
            return;
        }

        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        buffer.getInt(); // version
        buffer.getInt(); // reserved1
        int wrapMode = buffer.getInt();
        int clampColor = buffer.getInt();
        int objectClamp = buffer.getInt();
        buffer.getInt(); // reserved2

        float alpha = ((clampColor >>> 24) & 0xFF) / 255f;
        if (alpha < 0f) alpha = 0f;
        if (alpha > 1f) alpha = 1f;

        String warning = null;
        if (wrapMode != 0) {
            warning = "Image wrap modes not yet supported (wrapMode=" + wrapMode + ")";
        } else if (objectClamp != 0) {
            warning = "Image object clamp not yet supported (objectClamp=" + objectClamp + ")";
        }

        imageAttributesTable[objectId] = new ImageAttributesInfo(alpha, warning);
    }

    private void handleStringFormatObject(int objectId, byte[] payload) {
        if (objectId < 0 || objectId >= OBJECT_TABLE_SIZE) {
            LOGGER.fine(() -> "String format object id out of range: " + objectId);
            return;
        }
        if (payload == null || payload.length < 36) {
            LOGGER.fine("String format payload too small.");
            stringFormatTable[objectId] = null;
            return;
        }

        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        buffer.getInt(); // version
        int flags = buffer.getInt();
        buffer.getInt(); // language
        int alignment = buffer.getInt();
        int lineAlignment = buffer.getInt();
        buffer.getInt(); // digit substitution language
        buffer.getInt(); // digit substitution method
        buffer.getFloat(); // first tab offset
        int tabStopCount = buffer.getInt();
        int rangeCount = buffer.getInt();

        if (tabStopCount < 0 || rangeCount < 0) {
            LOGGER.fine("String format reported negative tab or range count.");
            stringFormatTable[objectId] = null;
            return;
        }

        int requiredTabBytes = tabStopCount * 4;
        if (buffer.remaining() < requiredTabBytes) {
            LOGGER.fine("String format tab stops truncated.");
            stringFormatTable[objectId] = null;
            return;
        }
        buffer.position(buffer.position() + requiredTabBytes);

        int requiredRangeBytes = rangeCount * 8;
        if (buffer.remaining() < requiredRangeBytes) {
            LOGGER.fine("String format character ranges truncated.");
            stringFormatTable[objectId] = null;
            return;
        }
        buffer.position(buffer.position() + requiredRangeBytes);

        boolean noWrap = (flags & STRING_FORMAT_FLAG_NO_WRAP) != 0;
        String warning = null;

        if ((flags & ~STRING_FORMAT_FLAG_NO_WRAP) != 0) {
            warning = "StringFormat flags include unsupported options (flags=0x" + Integer.toHexString(flags) + ")";
        }
        if (tabStopCount > 0 || rangeCount > 0) {
            warning = (warning == null ? "" : warning + "; ") + "Tab stops or character ranges not yet supported.";
        }

        stringFormatTable[objectId] = new StringFormatInfo(
                normalizeAlignment(alignment),
                normalizeAlignment(lineAlignment),
                noWrap,
                warning
        );
    }

    private void handleFontObject(int objectId, byte[] payload) {
        if (objectId < 0 || objectId >= OBJECT_TABLE_SIZE) {
            LOGGER.fine(() -> "Font object id out of range: " + objectId);
            return;
        }
        if (payload == null || payload.length < 24) {
            LOGGER.fine("Font payload too small.");
            fontTable[objectId] = null;
            return;
        }

        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        buffer.getInt(); // version (unused)
        float emSize = buffer.getFloat();
        int sizeUnit = buffer.getInt();
        int styleFlags = buffer.getInt();
        buffer.getInt(); // reserved
        int familyLength = buffer.getInt();

        if (familyLength <= 0 || familyLength > 1024) {
            LOGGER.fine("Font payload reported invalid family length: " + familyLength);
            fontTable[objectId] = null;
            return;
        }
        if (buffer.remaining() < familyLength * 2L) {
            LOGGER.fine("Font payload family data truncated.");
            fontTable[objectId] = null;
            return;
        }

        char[] familyChars = new char[familyLength];
        for (int i = 0; i < familyLength; i++) {
            familyChars[i] = (char) (buffer.getShort() & 0xFFFF);
        }
        String familyName = new String(familyChars).trim();
        if (familyName.isEmpty()) {
            familyName = "SansSerif";
        }

        float sizeInPoints = convertFontSize(emSize, sizeUnit);
        if (!Float.isFinite(sizeInPoints) || sizeInPoints <= 0f) {
            sizeInPoints = Math.max(emSize, 12f);
        }

        int style = Font.PLAIN;
        if ((styleFlags & 0x0001) != 0) {
            style |= Font.BOLD;
        }
        if ((styleFlags & 0x0002) != 0) {
            style |= Font.ITALIC;
        }

        boolean underline = (styleFlags & 0x0004) != 0;
        boolean strikeout = (styleFlags & 0x0008) != 0;

        Font font = new Font(familyName, style, Math.max(1, Math.round(sizeInPoints)));
        if (!font.getFamily().equalsIgnoreCase(familyName)) {
            font = new Font("SansSerif", style, Math.max(1, Math.round(sizeInPoints)));
        }
        font = font.deriveFont(style, sizeInPoints);
        fontTable[objectId] = font;

        if (underline || strikeout) {
            LOGGER.fine("Font underline/strikeout styles not yet supported.");
        }
    }

    private void handleRegionObject(int objectId, byte[] payload) {
        if (objectId < 0 || objectId >= OBJECT_TABLE_SIZE) {
            LOGGER.fine(() -> "Region object id out of range: " + objectId);
            return;
        }
        if (payload == null || payload.length < 8) {
            LOGGER.fine("Region payload too small.");
            regionTable[objectId] = null;
            return;
        }

        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        buffer.getInt(); // version
        buffer.getInt(); // region node count (may be zero)

        Area area = parseRegionNode(buffer);
        if (area == null) {
            LOGGER.fine("Failed to deserialize region data.");
            regionTable[objectId] = null;
            return;
        }

        regionTable[objectId] = area;
    }

    private Area parseRegionNode(ByteBuffer buffer) {
        if (buffer == null || buffer.remaining() < 4) {
            return null;
        }

        int type = buffer.getInt();

        CombineMode combineMode = CombineMode.fromCode(type);
        if (combineMode != null) {
            Area left = parseRegionNode(buffer);
            Area right = parseRegionNode(buffer);
            return combineAreas(left, right, combineMode);
        }

        switch (type) {
            case REGION_DATA_RECT:
                if (buffer.remaining() < 16) {
                    LOGGER.fine("Region rectangle node truncated.");
                    return null;
                }
                float x = buffer.getFloat();
                float y = buffer.getFloat();
                float width = buffer.getFloat();
                float height = buffer.getFloat();
                if (width <= 0 || height <= 0) {
                    return new Area();
                }
                return new Area(new Rectangle2D.Float(x, y, width, height));
            case REGION_DATA_PATH:
                if (buffer.remaining() < 4) {
                    LOGGER.fine("Region path node truncated.");
                    return null;
                }
                int pathLength = buffer.getInt();
                if (pathLength <= 0 || pathLength > buffer.remaining()) {
                    LOGGER.fine(() -> "Region path length invalid: " + pathLength);
                    return null;
                }
                byte[] pathBytes = new byte[pathLength];
                buffer.get(pathBytes);
                GeneralPath path = parsePathPayload(pathBytes);
                if (path == null) {
                    LOGGER.fine("Failed to decode region path.");
                    return null;
                }
                return new Area(path);
            case REGION_DATA_EMPTY_RECT:
                return new Area();
            case REGION_DATA_INFINITE_RECT:
                LOGGER.fine("Infinite region not supported; treating as empty.");
                return new Area();
            default:
                LOGGER.fine(() -> "Unsupported region node type: 0x" + Integer.toHexString(type));
                return null;
        }
    }

    private Area combineAreas(Area left, Area right, CombineMode mode) {
        Area leftCopy = left != null ? new Area(left) : null;
        Area rightCopy = right != null ? new Area(right) : null;

        switch (mode) {
            case REPLACE:
                return rightCopy != null ? rightCopy : new Area();
            case INTERSECT:
                if (leftCopy == null || rightCopy == null) {
                    return new Area();
                }
                leftCopy.intersect(rightCopy);
                return leftCopy;
            case UNION:
                if (leftCopy == null) {
                    return rightCopy != null ? rightCopy : new Area();
                }
                if (rightCopy != null) {
                    leftCopy.add(rightCopy);
                }
                return leftCopy;
            case XOR:
                if (leftCopy == null) {
                    return rightCopy != null ? rightCopy : new Area();
                }
                if (rightCopy != null) {
                    leftCopy.exclusiveOr(rightCopy);
                }
                return leftCopy;
            case EXCLUDE:
                if (leftCopy == null) {
                    return new Area();
                }
                if (rightCopy != null) {
                    leftCopy.subtract(rightCopy);
                }
                return leftCopy;
            case COMPLEMENT:
                if (rightCopy == null) {
                    return new Area();
                }
                if (leftCopy != null) {
                    rightCopy.subtract(leftCopy);
                }
                return rightCopy;
            default:
                return leftCopy != null ? leftCopy : (rightCopy != null ? rightCopy : new Area());
        }
    }

    private BufferedImage resolveImage(int imageId) {
        if (imageId < 0 || imageId >= OBJECT_TABLE_SIZE) {
            return null;
        }
        return imageTable[imageId];
    }

    private Font resolveFont(int fontId) {
        if (fontId < 0 || fontId >= OBJECT_TABLE_SIZE) {
            return null;
        }
        return fontTable[fontId];
    }

    private ImageAttributesInfo resolveImageAttributes(int attrId) {
        if (attrId < 0 || attrId >= OBJECT_TABLE_SIZE) {
            return null;
        }
        return imageAttributesTable[attrId];
    }

    private StringFormatInfo resolveStringFormat(int formatId) {
        if (formatId < 0 || formatId >= OBJECT_TABLE_SIZE) {
            return null;
        }
        return stringFormatTable[formatId];
    }

    private Area resolveRegion(int regionId) {
        if (regionId < 0 || regionId >= OBJECT_TABLE_SIZE) {
            return null;
        }
        return regionTable[regionId];
    }

    private BufferedImage buildBitmapFromPixelData(
            int width,
            int height,
            int stride,
            int pixelFormat,
            byte[] pixelData,
            int[] palette
    ) {
        if (width <= 0 || height <= 0 || pixelData == null) {
            return null;
        }

        final int bytesPerPixel;
        final boolean treatAsArgb;

        switch (pixelFormat) {
            case PIXEL_FORMAT_32BPP_ARGB:
            case PIXEL_FORMAT_32BPP_PARGB:
                bytesPerPixel = 4;
                treatAsArgb = true;
                break;
            case PIXEL_FORMAT_32BPP_RGB:
                bytesPerPixel = 4;
                treatAsArgb = false;
                break;
            case PIXEL_FORMAT_24BPP_RGB:
                bytesPerPixel = 3;
                treatAsArgb = false;
                break;
            case PIXEL_FORMAT_8BPP_INDEXED:
                bytesPerPixel = 1;
                treatAsArgb = true;
                if (palette == null || palette.length == 0) {
                    LOGGER.fine("Indexed bitmap missing palette data.");
                    return null;
                }
                break;
            default:
                LOGGER.fine(() -> "Bitmap pixel format unsupported: 0x" + Integer.toHexString(pixelFormat));
                return null;
        }

        int rowStride = stride;
        if (rowStride == 0) {
            rowStride = width * bytesPerPixel;
        }
        rowStride = Math.abs(rowStride);

        long expectedSize = (long) rowStride * height;
        if (pixelData.length < expectedSize) {
            if (pixelData.length == width * bytesPerPixel * height) {
                rowStride = width * bytesPerPixel;
            } else {
                LOGGER.fine(() -> "Bitmap pixel data shorter than expected (" + pixelData.length
                        + " bytes, expected at least " + expectedSize + ")");
                return null;
            }
        }

        BufferedImage image = new BufferedImage(width, height, BufferedImage.TYPE_INT_ARGB);
        int[] rowBuffer = new int[width];

        for (int y = 0; y < height; y++) {
            int rowOffset = y * rowStride;
            if (rowOffset + width * bytesPerPixel > pixelData.length) {
                LOGGER.fine("Bitmap row exceeds available pixel data.");
                return null;
            }

            for (int x = 0; x < width; x++) {
                int argb;
                int pixelOffset = rowOffset + x * bytesPerPixel;

                switch (pixelFormat) {
                    case PIXEL_FORMAT_32BPP_ARGB:
                    case PIXEL_FORMAT_32BPP_PARGB: {
                        int b = pixelData[pixelOffset] & 0xFF;
                        int g = pixelData[pixelOffset + 1] & 0xFF;
                        int r = pixelData[pixelOffset + 2] & 0xFF;
                        int a = pixelData[pixelOffset + 3] & 0xFF;
                        argb = (a << 24) | (r << 16) | (g << 8) | b;
                        break;
                    }
                    case PIXEL_FORMAT_32BPP_RGB: {
                        int b = pixelData[pixelOffset] & 0xFF;
                        int g = pixelData[pixelOffset + 1] & 0xFF;
                        int r = pixelData[pixelOffset + 2] & 0xFF;
                        argb = 0xFF000000 | (r << 16) | (g << 8) | b;
                        break;
                    }
                    case PIXEL_FORMAT_24BPP_RGB: {
                        int b = pixelData[pixelOffset] & 0xFF;
                        int g = pixelData[pixelOffset + 1] & 0xFF;
                        int r = pixelData[pixelOffset + 2] & 0xFF;
                        argb = 0xFF000000 | (r << 16) | (g << 8) | b;
                        break;
                    }
                    case PIXEL_FORMAT_8BPP_INDEXED: {
                        int index = pixelData[pixelOffset] & 0xFF;
                        if (index >= palette.length) {
                            argb = 0;
                        } else {
                            argb = palette[index];
                        }
                        // Ensure palette entries include alpha; if not, set to opaque.
                        if ((argb & 0xFF000000) == 0) {
                            argb |= 0xFF000000;
                        }
                        break;
                    }
                    default:
                        argb = 0;
                        break;
                }

                rowBuffer[x] = argb;
            }

            image.setRGB(0, y, width, 1, rowBuffer, 0, width);
        }

        return image;
    }

    private void handleDrawImage(int flags, byte[] payload) {
        int imageId = flags & 0xFF;
        BufferedImage image = resolveImage(imageId);
        if (image == null) {
            LOGGER.fine(() -> "DrawImage missing image object for id=" + imageId);
            return;
        }
        if (payload == null || payload.length < 24) {
            LOGGER.fine("DrawImage payload too small.");
            return;
        }

        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        int imageAttrId = buffer.getInt();
        buffer.getInt(); // src unit, ignored for now
        float srcX = buffer.getFloat();
        float srcY = buffer.getFloat();
        float srcWidth = buffer.getFloat();
        float srcHeight = buffer.getFloat();

        double destX;
        double destY;
        double destWidth;
        double destHeight;

        boolean compressedDest = (flags & 0x4000) != 0;
        if (compressedDest) {
            if (buffer.remaining() < 8) {
                LOGGER.fine("DrawImage compressed destination payload truncated.");
                return;
            }
            destX = buffer.getShort();
            destY = buffer.getShort();
            destWidth = buffer.getShort();
            destHeight = buffer.getShort();
        } else {
            if (buffer.remaining() < 16) {
                LOGGER.fine("DrawImage destination payload truncated.");
                return;
            }
            destX = buffer.getFloat();
            destY = buffer.getFloat();
            destWidth = buffer.getFloat();
            destHeight = buffer.getFloat();
        }

        if (destWidth == 0 || destHeight == 0) {
            return;
        }

        BufferedImage source = image;
        int sx = 0;
        int sy = 0;
        int sw = image.getWidth();
        int sh = image.getHeight();

        if (srcWidth > 0 && srcHeight > 0 &&
                (Math.abs(srcX) > 0.01 || Math.abs(srcY) > 0.01 ||
                        Math.abs(srcWidth - sw) > 0.01 || Math.abs(srcHeight - sh) > 0.01)) {
            sx = clampToRange(Math.round(srcX), 0, sw - 1);
            sy = clampToRange(Math.round(srcY), 0, sh - 1);
            sw = clampToRange(Math.round(srcWidth), 1, image.getWidth() - sx);
            sh = clampToRange(Math.round(srcHeight), 1, image.getHeight() - sy);
            try {
                source = image.getSubimage(sx, sy, sw, sh);
            } catch (RasterFormatException ex) {
                LOGGER.log(Level.FINE, "Invalid subimage bounds for DrawImage.", ex);
                source = image;
            }
        }

        AffineTransform transform = new AffineTransform();
        transform.translate(destX, destY);
        transform.scale(destWidth / source.getWidth(), destHeight / source.getHeight());

        ImageAttributesInfo attributes = resolveImageAttributes(imageAttrId);
        Composite originalComposite = graphics.getComposite();
        try {
            if (attributes != null && attributes.alpha < 1.0f) {
                graphics.setComposite(AlphaComposite.getInstance(AlphaComposite.SRC_OVER, attributes.alpha));
            }
            graphics.drawImage(source, transform, null);
        } finally {
            graphics.setComposite(originalComposite);
        }

        if (attributes != null && attributes.warning != null) {
            LOGGER.fine(() -> attributes.warning);
        }

        if ((imageAttrId & 0xFF) != 0) {
            // Already logged via attributes.warning if applicable.
        }
    }

    private void handleDrawString(int flags, byte[] payload) {
        if (payload == null || payload.length < 24) {
            LOGGER.fine("DrawString payload too small.");
            return;
        }

        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        int brushToken = buffer.getInt();
        int formatId = buffer.getInt();

        double layoutX;
        double layoutY;
        double layoutWidth;
        double layoutHeight;

        boolean compressedLayout = (flags & 0x4000) != 0;
        if (compressedLayout) {
            if (buffer.remaining() < 8) {
                LOGGER.fine("DrawString compressed layout payload truncated.");
                return;
            }
            layoutX = buffer.getShort();
            layoutY = buffer.getShort();
            layoutWidth = buffer.getShort();
            layoutHeight = buffer.getShort();
        } else {
            if (buffer.remaining() < 16) {
                LOGGER.fine("DrawString layout payload truncated.");
                return;
            }
            layoutX = buffer.getFloat();
            layoutY = buffer.getFloat();
            layoutWidth = buffer.getFloat();
            layoutHeight = buffer.getFloat();
        }

        if (buffer.remaining() < 4) {
            LOGGER.fine("DrawString payload missing character count.");
            return;
        }
        int charCount = buffer.getInt();
        if (charCount < 0) {
            LOGGER.fine("DrawString reported negative character count.");
            return;
        }

        int expectedBytes = charCount * 2;
        if (buffer.remaining() < expectedBytes) {
            LOGGER.fine("DrawString payload truncated for characters.");
            return;
        }

        byte[] textBytes = new byte[expectedBytes];
        buffer.get(textBytes);
        String text = new String(textBytes, StandardCharsets.UTF_16LE);
        text = text.replace('\u0000', ' ');

        Paint paint = (flags & 0x8000) != 0 ? new Color(brushToken, true) : resolveBrush(brushToken);
        if (paint == null) {
            LOGGER.fine(() -> "DrawString missing brush for id=" + brushToken);
            return;
        }

        StringFormatInfo format = resolveStringFormat(formatId);
        if (format != null && format.warning != null) {
            LOGGER.fine(() -> format.warning);
        }

        Paint originalPaint = graphics.getPaint();
        boolean noWrap = format != null && format.noWrap;
        graphics.setPaint(paint);

        try {
            FontMetrics metrics = graphics.getFontMetrics();
            double lineHeight = metrics.getHeight();
            double drawY = layoutY;
            String[] lines = text.split("\\r?\\n");
            double totalHeight = lines.length * lineHeight;

            if (layoutHeight > 0 && format != null) {
                switch (format.lineAlignment) {
                    case STRING_ALIGNMENT_CENTER:
                        drawY = layoutY + Math.max(0, (layoutHeight - totalHeight) / 2.0);
                        break;
                    case STRING_ALIGNMENT_FAR:
                        drawY = layoutY + Math.max(0, layoutHeight - totalHeight);
                        break;
                    default:
                        drawY = layoutY;
                        break;
                }
            }

            double boxWidth = layoutWidth > 0 ? layoutWidth : Double.MAX_VALUE;

            for (String line : lines) {
                if (line.isEmpty()) {
                    drawY += lineHeight;
                    continue;
                }
                double lineWidth = metrics.stringWidth(line);
                double drawX = layoutX;

                if (format != null) {
                    switch (format.alignment) {
                        case STRING_ALIGNMENT_CENTER:
                            drawX = layoutX + Math.max(0, (boxWidth - lineWidth) / 2.0);
                            break;
                        case STRING_ALIGNMENT_FAR:
                            drawX = layoutX + Math.max(0, boxWidth - lineWidth);
                            break;
                        default:
                            drawX = layoutX;
                    }
                }

                if (noWrap && lineWidth > boxWidth && boxWidth < Double.MAX_VALUE) {
                    // TODO: Implement trimming/ellipsis according to StringFormat. For now, log once.
                    if (format != null && !format.noWrapWarningLogged) {
                        LOGGER.fine("StringFormat NoWrap requested but text exceeds layout width; clipping output.");
                        format.noWrapWarningLogged = true;
                    }
                }

                float baseline = (float) (drawY + metrics.getAscent());
                graphics.drawString(line, (float) drawX, baseline);
                drawY += lineHeight;
                if (layoutHeight > 0 && drawY - layoutY > layoutHeight) {
                    break;
                }
            }
        } finally {
            graphics.setPaint(originalPaint);
        }

        if (formatId != 0) {
            LOGGER.fine(() -> "StringFormat objects are not yet supported (id=" + formatId + ")");
        }
    }

    private void handleDrawDriverString(int flags, byte[] payload) {
        if (payload == null || payload.length < 16) {
            LOGGER.fine("DrawDriverString payload too small.");
            return;
        }

        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        int brushToken = buffer.getInt();
        int optionFlags = buffer.getInt();
        int matrixPresent = buffer.getInt();
        int glyphCount = buffer.getInt();

        if (glyphCount <= 0) {
            LOGGER.fine("DrawDriverString reported non-positive glyph count.");
            return;
        }
        if (buffer.remaining() < glyphCount * 2L) {
            LOGGER.fine("DrawDriverString payload truncated for glyph data.");
            return;
        }

        char[] glyphEntries = new char[glyphCount];
        for (int i = 0; i < glyphCount; i++) {
            glyphEntries[i] = (char) (buffer.getShort() & 0xFFFF);
        }

        if (buffer.remaining() < glyphCount * 8L) {
            LOGGER.fine("DrawDriverString payload truncated for glyph positions.");
            return;
        }

        float[] xPositions = new float[glyphCount];
        float[] yPositions = new float[glyphCount];
        for (int i = 0; i < glyphCount; i++) {
            xPositions[i] = buffer.getFloat();
            yPositions[i] = buffer.getFloat();
        }

        AffineTransform driverTransform = null;
        if (matrixPresent != 0) {
            if (buffer.remaining() >= 24) {
                driverTransform = readAffineTransform(buffer);
            } else {
                LOGGER.fine("DrawDriverString matrix payload truncated.");
            }
        }

        Paint paint = (flags & 0x8000) != 0 ? new Color(brushToken, true) : resolveBrush(brushToken);
        if (paint == null) {
            paint = new Color(brushToken, true);
        }

        int fontId = flags & 0xFF;
        Font font = resolveFont(fontId);
        if (font == null) {
            font = graphics.getFont();
            LOGGER.fine(() -> "DrawDriverString missing font for id=" + fontId + ", using current graphics font.");
        }

        FontRenderContext frc = graphics.getFontRenderContext();
        GlyphVector glyphVector;
        try {
            if ((optionFlags & DRIVER_STRING_OPTION_CMAP_LOOKUP) != 0) {
                glyphVector = font.createGlyphVector(frc, glyphEntries);
            } else {
                int[] glyphCodes = new int[glyphCount];
                for (int i = 0; i < glyphCount; i++) {
                    glyphCodes[i] = glyphEntries[i] & 0xFFFF;
                }
                glyphVector = font.createGlyphVector(frc, glyphCodes);
            }
        } catch (Exception ex) {
            LOGGER.log(Level.FINE, "Unable to create glyph vector for DrawDriverString.", ex);
            return;
        }

        boolean useAdvance = (optionFlags & DRIVER_STRING_OPTION_REALIZED_ADVANCE) != 0;
        boolean limitSubpixel = (optionFlags & DRIVER_STRING_OPTION_LIMIT_SUBPIXEL) != 0;

        float advanceX = 0f;
        float advanceY = 0f;
        for (int i = 0; i < glyphCount; i++) {
            float x = xPositions[i];
            float y = yPositions[i];
            if (useAdvance) {
                advanceX += x;
                advanceY += y;
                x = advanceX;
                y = advanceY;
            }
            if (limitSubpixel) {
                x = Math.round(x);
                y = Math.round(y);
            }
            Point2D.Float position = new Point2D.Float(x, y);
            if (driverTransform != null) {
                driverTransform.transform(position, position);
            }
            glyphVector.setGlyphPosition(i, position);
        }

        Shape outline = glyphVector.getOutline();
        Paint originalPaint = graphics.getPaint();
        graphics.setPaint(paint);
        try {
            graphics.fill(outline);
        } finally {
            graphics.setPaint(originalPaint);
        }

        if ((optionFlags & DRIVER_STRING_OPTION_VERTICAL) != 0) {
            LOGGER.fine("Vertical driver string rendering relies on provided glyph positions.");
        }
        if (limitSubpixel) {
            LOGGER.fine("DriverStringOptionsLimitSubpixel applied via coordinate rounding.");
        }
    }


    private GeneralPath resolvePath(int pathId) {
        if (pathId < 0 || pathId >= OBJECT_TABLE_SIZE) {
            return null;
        }
        GeneralPath path = pathTable[pathId];
        if (path == null) {
            return null;
        }
        return (GeneralPath) path.clone();
    }

    private PenInfo resolvePen(int penId) {
        if (penId < 0 || penId >= OBJECT_TABLE_SIZE) {
            return null;
        }
        return penTable[penId];
    }

    private Paint parseBrushPayload(byte[] payload) {
        if (payload == null || payload.length < 8) {
            LOGGER.fine("Brush payload too small.");
            return null;
        }
        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        buffer.getInt(); // version
        int brushType = buffer.getInt();

        switch (brushType) {
            case BRUSH_TYPE_SOLID_COLOR:
                if (buffer.remaining() < 4) {
                    LOGGER.fine("Solid brush payload missing color data.");
                    return null;
                }
                int argb = buffer.getInt();
                return new Color(argb, true);
            case BRUSH_TYPE_LINEAR_GRADIENT:
                return parseLinearGradientBrush(buffer);
            case BRUSH_TYPE_PATH_GRADIENT:
                return parsePathGradientBrush(buffer);
            case BRUSH_TYPE_HATCH:
            case BRUSH_TYPE_TEXTURE:
                LOGGER.fine(() -> "Brush type " + brushType + " not yet supported.");
                return null;
            default:
                LOGGER.fine(() -> "Unsupported brush type: " + brushType);
                return null;
        }
    }

    private Paint parseLinearGradientBrush(ByteBuffer buffer) {
        if (buffer.remaining() < 40) {
            LOGGER.fine("Linear gradient brush payload too small.");
            return null;
        }

        int brushFlags = buffer.getInt();
        int wrapMode = buffer.getInt();
        float rectX = buffer.getFloat();
        float rectY = buffer.getFloat();
        float rectWidth = buffer.getFloat();
        float rectHeight = buffer.getFloat();
        int startColorArgb = buffer.getInt();
        int endColorArgb = buffer.getInt();
        buffer.getInt(); // reserved1
        buffer.getInt(); // reserved2

        AffineTransform gradientTransform = null;
        if ((brushFlags & BRUSH_DATA_TRANSFORM) != 0) {
            if (buffer.remaining() < 24) {
                LOGGER.fine("Linear gradient transform payload truncated.");
                return null;
            }
            gradientTransform = readAffineTransform(buffer);
        }

        int positionCount = 0;
        boolean hasPreset = (brushFlags & BRUSH_DATA_PRESET_COLORS) != 0;
        boolean hasBlendH = (brushFlags & BRUSH_DATA_BLEND_FACTORS_H) != 0;
        boolean hasBlendV = (brushFlags & BRUSH_DATA_BLEND_FACTORS_V) != 0;
        boolean hasFocus = (brushFlags & BRUSH_DATA_FOCUS_SCALES) != 0;
        boolean isGammaCorrected = (brushFlags & BRUSH_DATA_GAMMA) != 0;

        if (hasPreset || hasBlendH || hasBlendV) {
            if (buffer.remaining() < 4) {
                LOGGER.fine("Linear gradient optional data missing position count.");
                return null;
            }
            positionCount = buffer.getInt();
            if (positionCount <= 0 || positionCount > 4096) {
                LOGGER.fine("Linear gradient position count invalid: " + positionCount);
                positionCount = 0;
            }
        }

        float[] fractions = null;
        Color[] colors = null;

        if (hasPreset && positionCount > 0) {
            int requiredBytes = positionCount * (Float.BYTES + Integer.BYTES);
            if (buffer.remaining() < requiredBytes) {
                LOGGER.fine("Linear gradient preset data truncated.");
                return null;
            }
            fractions = new float[positionCount];
            colors = new Color[positionCount];
            for (int i = 0; i < positionCount; i++) {
                fractions[i] = clamp01(buffer.getFloat());
                colors[i] = new Color(buffer.getInt(), true);
            }
            sortGradientStops(fractions, colors);
            GradientStops deduped = dedupeGradientStops(fractions, colors);
            fractions = deduped.fractions();
            colors = deduped.colors();
            GradientStops stops = ensureBoundaryStops(fractions, colors);
            fractions = stops.fractions();
            colors = stops.colors();
        } else if (hasBlendH && positionCount > 0) {
            int requiredBytes = positionCount * Float.BYTES * 2;
            if (buffer.remaining() < requiredBytes) {
                LOGGER.fine("Linear gradient blend data truncated.");
                return null;
            }
            float[] positions = new float[positionCount];
            float[] blend = new float[positionCount];
            for (int i = 0; i < positionCount; i++) {
                positions[i] = clamp01(buffer.getFloat());
            }
            for (int i = 0; i < positionCount; i++) {
                blend[i] = clamp01(buffer.getFloat());
            }
            fractions = positions;
            colors = new Color[positionCount];
            Color start = new Color(startColorArgb, true);
            Color end = new Color(endColorArgb, true);
            for (int i = 0; i < positionCount; i++) {
                colors[i] = interpolateColor(start, end, blend[i]);
            }
            sortGradientStops(fractions, colors);
            GradientStops deduped = dedupeGradientStops(fractions, colors);
            fractions = deduped.fractions();
            colors = deduped.colors();
            GradientStops stops = ensureBoundaryStops(fractions, colors);
            fractions = stops.fractions();
            colors = stops.colors();
        } else if (hasBlendV && positionCount > 0) {
            int requiredBytes = positionCount * Float.BYTES * 2;
            if (buffer.remaining() < requiredBytes) {
                LOGGER.fine("Linear gradient vertical blend data truncated.");
                return null;
            }
            // Consume the data but fall back to a simple start/end gradient for now.
            for (int i = 0; i < positionCount * 2; i++) {
                buffer.getFloat();
            }
            LOGGER.fine("Linear gradient vertical blend factors not yet supported.");
        }

        if (hasFocus) {
            if (buffer.remaining() < 8) {
                LOGGER.fine("Linear gradient focus scale data truncated.");
                return null;
            }
            float focusX = buffer.getFloat();
            float focusY = buffer.getFloat();
            LOGGER.fine(() -> "Linear gradient focus scales not yet supported ("
                    + focusX + ", " + focusY + ").");
        }

        if (isGammaCorrected) {
            LOGGER.fine("Linear gradient gamma correction not yet supported.");
        }

        if ((brushFlags & BRUSH_DATA_DO_NOT_TRANSFORM) != 0) {
            LOGGER.fine("Linear gradient DoNotTransform flag not yet supported.");
        }

        if (fractions == null || colors == null) {
            fractions = new float[]{0f, 1f};
            colors = new Color[]{new Color(startColorArgb, true), new Color(endColorArgb, true)};
        }

        if (rectWidth == 0f && rectHeight == 0f) {
            LOGGER.fine("Linear gradient rectangle collapsed; using solid color fallback.");
            return colors[colors.length - 1];
        }

        Point2D startPoint = new Point2D.Float(rectX, rectY);
        Point2D endPoint;
        if (Math.abs(rectWidth) < 1e-3 && Math.abs(rectHeight) >= 1e-3) {
            endPoint = new Point2D.Float(rectX, rectY + rectHeight);
        } else {
            endPoint = new Point2D.Float(rectX + rectWidth, rectY);
            if (startPoint.distance(endPoint) < 1e-3 && Math.abs(rectHeight) >= 1e-3) {
                endPoint = new Point2D.Float(rectX, rectY + rectHeight);
            }
        }

        MultipleGradientPaint.CycleMethod cycleMethod = cycleMethodFromWrapMode(wrapMode);
        AffineTransform gradientTx = gradientTransform != null ? gradientTransform : new AffineTransform();

        try {
            return new LinearGradientPaint(
                    startPoint,
                    endPoint,
                    fractions,
                    colors,
                    cycleMethod,
                    MultipleGradientPaint.ColorSpaceType.SRGB,
                    gradientTx
            );
        } catch (IllegalArgumentException ex) {
            LOGGER.log(Level.FINE, "Failed to construct linear gradient paint, falling back to solid.", ex);
            return colors.length > 0 ? colors[colors.length - 1] : new Color(endColorArgb, true);
        }
    }

    private Paint parsePathGradientBrush(ByteBuffer buffer) {
        if (buffer.remaining() < 24) {
            LOGGER.fine("Path gradient brush payload too small.");
            return null;
        }

        int brushFlags = buffer.getInt();
        int wrapMode = buffer.getInt();
        Color centerColor = new Color(buffer.getInt(), true);
        float centerX = buffer.getFloat();
        float centerY = buffer.getFloat();
        int surroundingColorCount = buffer.getInt();

        if (surroundingColorCount < 0 || surroundingColorCount > 4096) {
            LOGGER.fine("Path gradient reported invalid surrounding color count: " + surroundingColorCount);
            surroundingColorCount = 0;
        }

        Color[] surroundingColors = new Color[surroundingColorCount];
        for (int i = 0; i < surroundingColorCount; i++) {
            if (buffer.remaining() < Integer.BYTES) {
                LOGGER.fine("Path gradient surrounding color array truncated.");
                return centerColor;
            }
            surroundingColors[i] = new Color(buffer.getInt(), true);
        }

        Color outerColor = surroundingColors.length > 0 ? averageColors(surroundingColors) : centerColor;
        if (outerColor == null) {
            outerColor = centerColor;
        }

        Shape boundaryShape = null;
        if ((brushFlags & BRUSH_DATA_PATH) != 0) {
            if (buffer.remaining() < Integer.BYTES) {
                LOGGER.fine("Path gradient boundary path size missing.");
                return centerColor;
            }
            int boundarySize = buffer.getInt();
            if (boundarySize < 0 || boundarySize > buffer.remaining()) {
                LOGGER.fine("Path gradient boundary path data truncated.");
                return centerColor;
            }
            byte[] boundaryBytes = new byte[boundarySize];
            buffer.get(boundaryBytes);
            boundaryShape = parsePathPayload(boundaryBytes);
        } else {
            LOGGER.fine("Path gradient boundary point data not yet supported.");
            buffer.position(buffer.limit());
            return createPathGradientFallback(centerColor, surroundingColors, wrapMode);
        }

        AffineTransform optionalTransform = null;
        if ((brushFlags & BRUSH_DATA_TRANSFORM) != 0) {
            if (buffer.remaining() >= 24) {
                optionalTransform = readAffineTransform(buffer);
            } else {
                LOGGER.fine("Path gradient transform payload truncated.");
            }
        }

        List<Float> fractionList = new ArrayList<>();
        List<Color> colorList = new ArrayList<>();
        fractionList.add(0f);
        colorList.add(centerColor);

        if ((brushFlags & BRUSH_DATA_PRESET_COLORS) != 0) {
            GradientStops presetStops = readPathGradientPresetStops(buffer);
            if (presetStops != null) {
                float[] presetFractions = presetStops.fractions();
                Color[] presetColors = presetStops.colors();
                for (int i = 0; i < presetFractions.length; i++) {
                    fractionList.add(clamp01(presetFractions[i]));
                    colorList.add(presetColors[i]);
                }
            } else {
                LOGGER.fine("Failed to parse path gradient preset stops; continuing without them.");
            }
        }

        if ((brushFlags & BRUSH_DATA_BLEND_FACTORS_H) != 0) {
            GradientBlend blend = readPathGradientBlend(buffer);
            if (blend != null) {
                float[] blendFractions = blend.fractions();
                float[] blendFactors = blend.factors();
                for (int i = 0; i < blendFractions.length; i++) {
                    fractionList.add(clamp01(blendFractions[i]));
                    colorList.add(interpolateColor(centerColor, outerColor, blendFactors[i]));
                }
            } else {
                LOGGER.fine("Failed to parse path gradient blend factors; continuing with default blend.");
            }
        }

        Double focusScaleX = null;
        Double focusScaleY = null;
        if ((brushFlags & BRUSH_DATA_FOCUS_SCALES) != 0) {
            if (buffer.remaining() >= Float.BYTES * 2) {
                focusScaleX = (double) buffer.getFloat();
                focusScaleY = (double) buffer.getFloat();
            } else {
                LOGGER.fine("Path gradient focus scales payload truncated.");
            }
        }

        if ((brushFlags & BRUSH_DATA_GAMMA) != 0) {
            LOGGER.fine("Path gradient gamma correction flag currently ignored.");
        }

        if ((brushFlags & BRUSH_DATA_DO_NOT_TRANSFORM) != 0) {
            LOGGER.fine("Path gradient DoNotTransform flag currently ignored.");
        }

        fractionList.add(1f);
        colorList.add(outerColor);

        float[] fractions = new float[fractionList.size()];
        Color[] gradientColors = new Color[colorList.size()];
        for (int i = 0; i < fractionList.size(); i++) {
            fractions[i] = clamp01(fractionList.get(i));
            gradientColors[i] = colorList.get(i);
        }

        GradientStops dedupedStops = dedupeGradientStops(fractions, gradientColors);
        GradientStops normalizedStops = ensureBoundaryStops(dedupedStops.fractions(), dedupedStops.colors());
        fractions = normalizedStops.fractions();
        gradientColors = normalizedStops.colors();

        if (buffer.hasRemaining()) {
            LOGGER.fine(() -> "Path gradient brush left " + buffer.remaining() + " unread optional bytes; skipping.");
            buffer.position(buffer.limit());
        }
        if (boundaryShape == null) {
            LOGGER.fine("Path gradient boundary could not be resolved; using solid fallback.");
            return createPathGradientFallback(centerColor, surroundingColors, wrapMode);
        }

        Rectangle2D bounds = boundaryShape.getBounds2D();
        if (bounds.isEmpty()) {
            LOGGER.fine("Path gradient boundary bounds empty; using solid fallback.");
            return createPathGradientFallback(centerColor, surroundingColors, wrapMode);
        }

        Point2D centerPoint = new Point2D.Float(centerX, centerY);
        double radiusCandidate = Math.max(
                Math.max(centerPoint.distance(bounds.getMinX(), bounds.getMinY()),
                        centerPoint.distance(bounds.getMinX(), bounds.getMaxY())),
                Math.max(centerPoint.distance(bounds.getMaxX(), bounds.getMinY()),
                        centerPoint.distance(bounds.getMaxX(), bounds.getMaxY()))
        );

        float radius = (float) radiusCandidate;
        if (radius <= 1e-3f) {
            LOGGER.fine("Path gradient computed radius too small; using solid fallback.");
            return createPathGradientFallback(centerColor, surroundingColors, wrapMode);
        }

        MultipleGradientPaint.CycleMethod cycleMethod = cycleMethodFromWrapMode(wrapMode);
        AffineTransform gradientTx = optionalTransform != null ? new AffineTransform(optionalTransform) : new AffineTransform();

        if (focusScaleX != null && focusScaleY != null) {
            double sx = normalizeFocusScale(focusScaleX);
            double sy = normalizeFocusScale(focusScaleY);
            AffineTransform focusTx = new AffineTransform();
            focusTx.translate(centerPoint.getX(), centerPoint.getY());
            focusTx.scale(sx, sy);
            focusTx.translate(-centerPoint.getX(), -centerPoint.getY());
            gradientTx.preConcatenate(focusTx);
        }

        try {
            return new RadialGradientPaint(
                    centerPoint,
                    radius,
                    centerPoint,
                    fractions,
                    gradientColors,
                    cycleMethod,
                    MultipleGradientPaint.ColorSpaceType.SRGB,
                    gradientTx
            );
        } catch (IllegalArgumentException ex) {
            LOGGER.log(Level.FINE, "Failed to construct path gradient paint, using solid fallback.", ex);
            return outerColor;
        }
    }

    private GeneralPath parsePathPayload(byte[] payload) {
        if (payload == null || payload.length < 12) {
            LOGGER.fine("Path payload too small.");
            return null;
        }

        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        buffer.getInt(); // version
        int pointCount = buffer.getInt();
        int pathFlags = buffer.getInt();

        if (pointCount <= 0) {
            return new GeneralPath();
        }

        if ((pathFlags & 0x800) != 0) {
            LOGGER.fine("RLE path encoding not supported yet.");
            return null;
        }

        boolean compressed = (pathFlags & 0x4000) != 0;
        if (compressed) {
            LOGGER.fine("Compressed path points not supported yet.");
            return null;
        }

        int coordinateBytes = pointCount * 8;
        if (buffer.remaining() < coordinateBytes + pointCount) {
            LOGGER.fine("Path payload truncated.");
            return null;
        }

        double[] coords = new double[pointCount * 2];
        for (int i = 0; i < pointCount; i++) {
            coords[i * 2] = buffer.getFloat();
            coords[i * 2 + 1] = buffer.getFloat();
        }
        byte[] types = new byte[pointCount];
        buffer.get(types);

        GeneralPath path = new GeneralPath();
        int i = 0;
        while (i < pointCount) {
            double x = coords[i * 2];
            double y = coords[i * 2 + 1];
            int type = types[i] & 0x07;
            boolean close = (types[i] & 0x80) != 0;

            switch (type) {
                case 0: // start
                    path.moveTo(x, y);
                    break;
                case 1: // line
                    path.lineTo(x, y);
                    if (close) {
                        path.closePath();
                    }
                    break;
                case 3: // bezier
                    if (i + 2 >= pointCount) {
                        LOGGER.fine("Bezier path segment truncated.");
                        return path;
                    }
                    double cx1 = coords[i * 2];
                    double cy1 = coords[i * 2 + 1];
                    double cx2 = coords[(i + 1) * 2];
                    double cy2 = coords[(i + 1) * 2 + 1];
                    double ex = coords[(i + 2) * 2];
                    double ey = coords[(i + 2) * 2 + 1];
                    path.curveTo(cx1, cy1, cx2, cy2, ex, ey);
                    if ((types[i + 2] & 0x80) != 0) {
                        path.closePath();
                    }
                    i += 2;
                    break;
                default:
                    LOGGER.fine(() -> "Unsupported path point type: " + type);
                    return path;
            }

            i += 1;
        }

        return path;
    }

    private void handleSetClipRect(int flags, byte[] payload) {
        if (payload == null || payload.length < 16) {
            LOGGER.fine("SetClipRect payload too small.");
            return;
        }

        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        double x = buffer.getFloat();
        double y = buffer.getFloat();
        double width = buffer.getFloat();
        double height = buffer.getFloat();

        Shape rect = new Rectangle2D.Double(x, y, width, height);
        applyClip(rect, decodeCombineMode(flags));
    }

    private void handleSetClipPath(int flags, byte[] payload) {
        int pathId = flags & 0xFF;
        GeneralPath path = resolvePath(pathId);
        if (path == null) {
            LOGGER.fine(() -> "SetClipPath missing path for id=" + pathId);
            return;
        }
        applyClip(path, decodeCombineMode(flags));
    }

    private void handleSetClipRegion(int flags, byte[] payload) {
        int regionId = flags & 0xFF;
        Area regionArea = resolveRegion(regionId);
        if (regionArea == null) {
            LOGGER.fine(() -> "SetClipRegion missing region for id=" + regionId);
            return;
        }
        applyClip(regionArea, decodeCombineMode(flags));
    }

    private void resetClip() {
        graphics.setClip(null);
    }

    private CombineMode decodeCombineMode(int flags) {
        int modeCode = (flags >> 8) & 0xF;
        return CombineMode.fromCode(modeCode);
    }

    private void applyClip(Shape newShape, CombineMode mode) {
        if (newShape == null) {
            return;
        }

        Shape currentClip = graphics.getClip();
        if (currentClip == null || mode == CombineMode.REPLACE) {
            graphics.setClip(newShape);
            return;
        }

        Area currentArea = new Area(currentClip);
        Area newArea = new Area(newShape);

        switch (mode) {
            case INTERSECT:
                currentArea.intersect(newArea);
                break;
            case UNION:
                currentArea.add(newArea);
                break;
            case XOR:
                currentArea.exclusiveOr(newArea);
                break;
            case EXCLUDE:
                currentArea.subtract(newArea);
                break;
            case COMPLEMENT:
                newArea.subtract(currentArea);
                currentArea = newArea;
                break;
            case REPLACE:
                currentArea = newArea;
                break;
            default:
                LOGGER.fine(() -> "Unsupported combine mode: " + mode);
                return;
        }

        graphics.setClip(currentArea);
    }

    private void handleSave(byte[] payload) {
        int stackIndex = readStackIndex(payload);
        Area clipArea = null;
        Shape currentClip = graphics.getClip();
        if (currentClip != null) {
            clipArea = new Area(currentClip);
        }
        GraphicsState state = new GraphicsState(
                stackIndex,
                new AffineTransform(worldTransform),
                clipArea
        );
        stateStack.push(state);
    }

    private void handleRestore(byte[] payload) {
        int stackIndex = readStackIndex(payload);
        GraphicsState state = popGraphicsState(stackIndex);
        if (state == null) {
            LOGGER.fine(() -> "Restore requested for unknown state index: " + stackIndex);
            return;
        }
        worldTransform.setTransform(state.transform);
        graphics.setTransform(worldTransform);
        if (state.clip != null) {
            graphics.setClip(new Area(state.clip));
        } else {
            graphics.setClip(null);
        }
    }

    private int readStackIndex(byte[] payload) {
        if (payload == null || payload.length < 4) {
            return -1;
        }
        ByteBuffer buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
        return buffer.getInt();
    }

    private GraphicsState popGraphicsState(int stackIndex) {
        if (stateStack.isEmpty()) {
            return null;
        }
        if (stackIndex < 0) {
            return stateStack.pollFirst();
        }
        Iterator<GraphicsState> iterator = stateStack.iterator();
        while (iterator.hasNext()) {
            GraphicsState state = iterator.next();
            if (state.stackIndex == stackIndex) {
                iterator.remove();
                return state;
            }
        }
        return null;
    }

    private int clampToRange(int value, int min, int max) {
        if (max < min) {
            return min;
        }
        if (value < min) {
            return min;
        }
        if (value > max) {
            return max;
        }
        return value;
    }

    private int normalizeAlignment(int alignment) {
        if (alignment < STRING_ALIGNMENT_NEAR || alignment > STRING_ALIGNMENT_FAR) {
            return STRING_ALIGNMENT_NEAR;
        }
        return alignment;
    }

    private void resetWorldTransform() {
        worldTransform.setTransform(baseTransform);
        graphics.setTransform(worldTransform);
    }

    private void applyDeltaTransform(AffineTransform delta, MatrixOrder order) {
        if (order == MatrixOrder.PREPEND) {
            worldTransform.preConcatenate(delta);
        } else {
            worldTransform.concatenate(delta);
        }
        graphics.setTransform(worldTransform);
    }

    private MatrixOrder decodeMatrixOrder(int flags) {
        // Bit 13 (0x2000) indicates append semantics in EMF+/GDI+.
        return (flags & 0x2000) != 0 ? MatrixOrder.APPEND : MatrixOrder.PREPEND;
    }

    private enum MatrixOrder {
        PREPEND,
        APPEND
    }

    private static final class GradientStops {
        private final float[] fractions;
        private final Color[] colors;

        private GradientStops(float[] fractions, Color[] colors) {
            this.fractions = fractions;
            this.colors = colors;
        }

        private float[] fractions() {
            return fractions;
        }

        private Color[] colors() {
            return colors;
        }
    }

    private static final class GradientBlend {
        private final float[] fractions;
        private final float[] factors;

        private GradientBlend(float[] fractions, float[] factors) {
            this.fractions = fractions;
            this.factors = factors;
        }

        private float[] fractions() {
            return fractions;
        }

        private float[] factors() {
            return factors;
        }
    }

    private enum CombineMode {
        REPLACE(0),
        INTERSECT(1),
        UNION(2),
        XOR(3),
        EXCLUDE(4),
        COMPLEMENT(5);

        private final int code;

        CombineMode(int code) {
            this.code = code;
        }

        static CombineMode fromCode(int code) {
            for (CombineMode mode : values()) {
                if (mode.code == code) {
                    return mode;
                }
            }
            return REPLACE;
        }
    }

    private static final class GraphicsState {
        private final int stackIndex;
        private final AffineTransform transform;
        private final Area clip;

        private GraphicsState(int stackIndex, AffineTransform transform, Area clip) {
            this.stackIndex = stackIndex;
            this.transform = transform;
            this.clip = clip;
        }
    }

    private static final class ImageAttributesInfo {
        private final float alpha;
        private final String warning;

        private ImageAttributesInfo(float alpha, String warning) {
            this.alpha = alpha;
            this.warning = warning;
        }
    }

    private static final class StringFormatInfo {
        private final int alignment;
        private final int lineAlignment;
        private final boolean noWrap;
        private final String warning;
        private boolean noWrapWarningLogged = false;

        private StringFormatInfo(int alignment, int lineAlignment, boolean noWrap, String warning) {
            this.alignment = alignment;
            this.lineAlignment = lineAlignment;
            this.noWrap = noWrap;
            this.warning = warning;
        }
    }

    private static final class PenInfo {
        private final Paint paint;
        private final BasicStroke stroke;

        PenInfo(Paint paint, float width) {
            this.paint = paint;
            this.stroke = new BasicStroke(width, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND);
        }

        Paint paint() {
            return paint;
        }

        BasicStroke stroke() {
            return stroke;
        }
    }
}

