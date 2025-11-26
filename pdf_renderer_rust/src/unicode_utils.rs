//! Unicode utilities for PDF text rendering
//! 
//! Provides conversion from Unicode (UTF-8) to PDF text encoding (WinAnsiEncoding)
//! with support for Polish characters and other Latin-1 extended characters.

/// Check if text contains Polish characters
pub fn has_polish_chars(text: &str) -> bool {
    text.chars().any(|ch| matches!(ch,
        'ą' | 'ć' | 'ę' | 'ł' | 'ń' | 'ó' | 'ś' | 'ź' | 'ż' |
        'Ą' | 'Ć' | 'Ę' | 'Ł' | 'Ń' | 'Ó' | 'Ś' | 'Ź' | 'Ż'
    ))
}

/// Convert Unicode string to WinAnsiEncoding bytes for PDF text rendering
/// 
/// WinAnsiEncoding is a superset of ISO 8859-1 (Latin-1) and includes
/// Polish characters: ą, ć, ę, ł, ń, ó, ś, ź, ż
/// 
/// Characters not in WinAnsiEncoding are replaced with '?' or removed.
pub fn unicode_to_winansi(text: &str) -> Vec<u8> {
    let mut result = Vec::with_capacity(text.len());
    
    for ch in text.chars() {
        let byte = match ch {
            // Standard ASCII (0x00-0x7F)
            ch if ch as u32 <= 0x7F => ch as u8,
            
            // WinAnsiEncoding extended characters (0x80-0xFF)
            // Polish characters
            'Ą' => 0xA5, // Ą -> 0xA5
            'ą' => 0xB9, // ą -> 0xB9
            'Ć' => 0xC6, // Ć -> 0xC6
            'ć' => 0xE6, // ć -> 0xE6
            'Ę' => 0xCA, // Ę -> 0xCA
            'ę' => 0xEA, // ę -> 0xEA
            'Ł' => 0xA3, // Ł -> 0xA3
            'ł' => 0xB3, // ł -> 0xB3
            'Ń' => 0xD1, // Ń -> 0xD1
            'ń' => 0xF1, // ń -> 0xF1
            'Ó' => 0xD3, // Ó -> 0xD3
            'ó' => 0xF3, // ó -> 0xF3
            'Ś' => 0x8C, // Ś -> 0x8C
            'ś' => 0x9C, // ś -> 0x9C
            'Ź' => 0x8F, // Ź -> 0x8F
            'ź' => 0x9F, // ź -> 0x9F
            'Ż' => 0xAF, // Ż -> 0xAF
            'ż' => 0xBF, // ż -> 0xBF
            
            // Other Latin-1 extended characters
            '€' => 0x80,
            '‚' => 0x82,
            'ƒ' => 0x83,
            '„' => 0x84,
            '…' => 0x85,
            '†' => 0x86,
            '‡' => 0x87,
            'ˆ' => 0x88,
            '‰' => 0x89,
            'Š' => 0x8A,
            '‹' => 0x8B,
            'Œ' => 0x8C,
            'Ž' => 0x8E,
            '\u{2018}' => 0x91, // Left single quotation mark
            '\u{2019}' => 0x92, // Right single quotation mark
            '\u{201C}' => 0x93, // Left double quotation mark
            '\u{201D}' => 0x94, // Right double quotation mark
            '•' => 0x95,
            '–' => 0x96,
            '—' => 0x97,
            '˜' => 0x98,
            '™' => 0x99,
            'š' => 0x9A,
            '›' => 0x9B,
            'œ' => 0x9C,
            'ž' => 0x9E,
            'Ÿ' => 0x9F,
            '¡' => 0xA1,
            '¢' => 0xA2,
            '£' => 0xA3,
            '¤' => 0xA4,
            '¥' => 0xA5,
            '¦' => 0xA6,
            '§' => 0xA7,
            '¨' => 0xA8,
            '©' => 0xA9,
            'ª' => 0xAA,
            '«' => 0xAB,
            '¬' => 0xAC,
            '­' => 0xAD,
            '®' => 0xAE,
            '¯' => 0xAF,
            '°' => 0xB0,
            '±' => 0xB1,
            '²' => 0xB2,
            '³' => 0xB3,
            '´' => 0xB4,
            'µ' => 0xB5,
            '¶' => 0xB6,
            '·' => 0xB7,
            '¸' => 0xB8,
            '¹' => 0xB9,
            'º' => 0xBA,
            '»' => 0xBB,
            '¼' => 0xBC,
            '½' => 0xBD,
            '¾' => 0xBE,
            '¿' => 0xBF,
            'À' => 0xC0,
            'Á' => 0xC1,
            'Â' => 0xC2,
            'Ã' => 0xC3,
            'Ä' => 0xC4,
            'Å' => 0xC5,
            'Æ' => 0xC6,
            'Ç' => 0xC7,
            'È' => 0xC8,
            'É' => 0xC9,
            'Ê' => 0xCA,
            'Ë' => 0xCB,
            'Ì' => 0xCC,
            'Í' => 0xCD,
            'Î' => 0xCE,
            'Ï' => 0xCF,
            'Ð' => 0xD0,
            'Ñ' => 0xD1,
            'Ò' => 0xD2,
            // 'Ó' => 0xD3, // Already handled above for Polish
            'Ô' => 0xD4,
            'Õ' => 0xD5,
            'Ö' => 0xD6,
            '×' => 0xD7,
            'Ø' => 0xD8,
            'Ù' => 0xD9,
            'Ú' => 0xDA,
            'Û' => 0xDB,
            'Ü' => 0xDC,
            'Ý' => 0xDD,
            'Þ' => 0xDE,
            'ß' => 0xDF,
            'à' => 0xE0,
            'á' => 0xE1,
            'â' => 0xE2,
            'ã' => 0xE3,
            'ä' => 0xE4,
            'å' => 0xE5,
            'æ' => 0xE6,
            'ç' => 0xE7,
            'è' => 0xE8,
            'é' => 0xE9,
            // 'ê' => 0xEA, // Already handled above for Polish (ę)
            'ë' => 0xEB,
            'ì' => 0xEC,
            'í' => 0xED,
            'î' => 0xEE,
            'ï' => 0xEF,
            'ð' => 0xF0,
            // 'ñ' => 0xF1, // Already handled above for Polish (ń)
            'ò' => 0xF2,
            // 'ó' => 0xF3, // Already handled above for Polish
            'ô' => 0xF4,
            'õ' => 0xF5,
            'ö' => 0xF6,
            '÷' => 0xF7,
            'ø' => 0xF8,
            'ù' => 0xF9,
            'ú' => 0xFA,
            'û' => 0xFB,
            'ü' => 0xFC,
            'ý' => 0xFD,
            'þ' => 0xFE,
            'ÿ' => 0xFF,
            
            // Characters not in WinAnsiEncoding - replace with '?'
            _ => b'?',
        };
        
        result.push(byte);
    }
    
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_polish_characters() {
        let text = "ą ć ę ł ń ó ś ź ż";
        let result = unicode_to_winansi(text);
        // Check that Polish characters are converted correctly
        assert_eq!(result, vec![0xB9, 0x20, 0xE6, 0x20, 0xEA, 0x20, 0xB3, 0x20, 0xF1, 0x20, 0xF3, 0x20, 0x9C, 0x20, 0x9F, 0x20, 0xBF]);
    }
    
    #[test]
    fn test_ascii() {
        let text = "Hello World";
        let result = unicode_to_winansi(text);
        assert_eq!(result, text.as_bytes());
    }
    
    #[test]
    fn test_mixed() {
        let text = "Zamawiającego";
        let result = unicode_to_winansi(text);
        // Z a m a w i a j ą c e g o
        assert_eq!(result[0], b'Z');
        assert_eq!(result[10], 0xB9); // ą
    }
}

