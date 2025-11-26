package com.doclingforge.emfconverter.emfplus;

import java.util.HashMap;
import java.util.Map;

public enum EmfPlusRecordType {
    UNKNOWN(-1),
    INVALID(0x4000),
    HEADER(0x4001),
    END_OF_FILE(0x4002),
    COMMENT(0x4003),
    GET_DC(0x4004),
    MULTI_FORMAT_START(0x4005),
    MULTI_FORMAT_SECTION(0x4006),
    MULTI_FORMAT_END(0x4007),
    OBJECT(0x4008),
    CLEAR(0x4009),
    FILL_RECTS(0x400A),
    DRAW_RECTS(0x400B),
    FILL_POLYGON(0x400C),
    DRAW_LINES(0x400D),
    FILL_ELLIPSE(0x400E),
    DRAW_ELLIPSE(0x400F),
    FILL_PIE(0x4010),
    DRAW_PIE(0x4011),
    DRAW_ARC(0x4012),
    FILL_REGION(0x4013),
    FILL_PATH(0x4014),
    DRAW_PATH(0x4015),
    FILL_CLOSED_CURVE(0x4016),
    DRAW_CLOSED_CURVE(0x4017),
    DRAW_CURVE(0x4018),
    DRAW_BEZIERS(0x4019),
    DRAW_IMAGE(0x401A),
    DRAW_IMAGE_POINTS(0x401B),
    DRAW_STRING(0x401C),
    SET_RENDERING_ORIGIN(0x401D),
    SET_ANTI_ALIAS_MODE(0x401E),
    SET_TEXT_RENDERING_HINT(0x401F),
    SET_TEXT_CONTRAST(0x4020),
    SET_INTERPOLATION_MODE(0x4021),
    SET_PIXEL_OFFSET_MODE(0x4022),
    SET_COMPOSITING_MODE(0x4023),
    SET_COMPOSITING_QUALITY(0x4024),
    SAVE(0x4025),
    RESTORE(0x4026),
    BEGIN_CONTAINER(0x4027),
    BEGIN_CONTAINER_NO_PARAMS(0x4028),
    END_CONTAINER(0x4029),
    SET_WORLD_TRANSFORM(0x402A),
    RESET_WORLD_TRANSFORM(0x402B),
    MULTIPLY_WORLD_TRANSFORM(0x402C),
    TRANSLATE_WORLD_TRANSFORM(0x402D),
    SCALE_WORLD_TRANSFORM(0x402E),
    ROTATE_WORLD_TRANSFORM(0x402F),
    SET_PAGE_TRANSFORM(0x4030),
    RESET_CLIP(0x4031),
    SET_CLIP_RECT(0x4032),
    SET_CLIP_PATH(0x4033),
    SET_CLIP_REGION(0x4034),
    OFFSET_CLIP(0x4035),
    DRAW_DRIVER_STRING(0x4036);

    private static final Map<Integer, EmfPlusRecordType> LOOKUP = new HashMap<>();

    static {
        for (EmfPlusRecordType type : values()) {
            LOOKUP.put(type.code, type);
        }
    }

    private final int code;

    EmfPlusRecordType(int code) {
        this.code = code;
    }

    public int getCode() {
        return code;
    }

    public static EmfPlusRecordType fromCode(int code) {
        return LOOKUP.getOrDefault(code, UNKNOWN);
    }
}

