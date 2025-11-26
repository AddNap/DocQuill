package com.doclingforge.emfconverter.emfplus;

import java.util.HashMap;
import java.util.Map;

/**
 * Subset of EMF+ object table entry types that we care about for rendering.
 */
public enum EmfPlusObjectType {
    INVALID(0x00),
    BRUSH(0x01),
    PEN(0x02),
    PATH(0x03),
    REGION(0x04),
    IMAGE(0x05),
    FONT(0x06),
    STRING_FORMAT(0x07),
    IMAGE_ATTRIBUTES(0x08),
    CUSTOM_LINE_CAP(0x09);

    private static final Map<Integer, EmfPlusObjectType> LOOKUP = new HashMap<>();

    static {
        for (EmfPlusObjectType type : values()) {
            LOOKUP.put(type.code, type);
        }
    }

    private final int code;

    EmfPlusObjectType(int code) {
        this.code = code;
    }

    public static EmfPlusObjectType fromCode(int code) {
        return LOOKUP.getOrDefault(code, INVALID);
    }
}


