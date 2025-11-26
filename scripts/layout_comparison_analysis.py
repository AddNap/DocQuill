"""
Analiza porównawcza: LayoutEngine vs DirectPDFRenderer

Porównanie logiki obliczania pozycji, wysokości i edge cases.
"""

from typing import Dict, Any, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class LayoutComparison:
    """Porównanie logiki obliczania między LayoutEngine a DirectPDFRenderer."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_direct_pdf_renderer_logic(self) -> Dict[str, Any]:
        """Analizuje logikę obliczania w DirectPDFRenderer."""
        
        analysis = {
            "page_setup": {
                "page_dimensions": {
                    "logic": "A4 = (595.28, 841.89), Letter = letter, fallback A4",
                    "edge_cases": [
                        "Nieznany page_size → fallback A4",
                        "Page size z DOCX section properties override domyślne"
                    ]
                },
                "margins": {
                    "default": "2.5cm all around (70.87pt)",
                    "docx_override": "Ładowane z document.section.properties",
                    "dynamic_footer": "margin_bottom = footer_start_from_bottom + footer_height + spacing",
                    "edge_cases": [
                        "Brak section properties → użyj domyślnych",
                        "Footer height = 0 → minimum 30pt",
                        "Footer margin z DOCX → konwersja twips→points"
                    ]
                }
            },
            
            "positioning_logic": {
                "initial_position": {
                    "x": "self.margin_left",
                    "y": "self.page_height - self.margin_top",
                    "edge_cases": [
                        "Y zaczyna od góry strony (ReportLab coordinate system)",
                        "Pozycja resetowana przy każdej nowej stronie"
                    ]
                },
                "element_positioning": {
                    "paragraphs": "self.y -= line.height (po każdej linii)",
                    "tables": "self.y = new_y (po całej tabeli)",
                    "anchored_images": "Absolutna pozycja niezależna od flow",
                    "edge_cases": [
                        "Page break w środku paragrafu → _new_page()",
                        "Widows/orphans control dla numerowanych paragrafów",
                        "Anchored images nie wpływają na flow"
                    ]
                }
            },
            
            "height_calculation": {
                "paragraphs": {
                    "method": "TextBreaker.break_paragraph() + line heights",
                    "factors": [
                        "Font size × line_spacing_multiplier",
                        "Space before/after",
                        "Indentation (nie wpływa na wysokość)",
                        "Justification (nie wpływa na wysokość)"
                    ],
                    "edge_cases": [
                        "Empty paragraph → minimalna wysokość",
                        "Paragraph z tylko anchored images → pomiń tekst",
                        "Line spacing auto vs exact"
                    ]
                },
                "tables": {
                    "method": "Suma wysokości wierszy",
                    "row_height": "Max wysokość komórek w wierszu",
                    "cell_height": "Suma wysokości paragrafów w komórce",
                    "edge_cases": [
                        "Empty table → return early",
                        "Merged cells → uwzględnij colspan/rowspan",
                        "Table width auto-fit do page width"
                    ]
                },
                "images": {
                    "inline": "Wysokość linii tekstu",
                    "anchored": "Wymiary z DOCX (EMU → points)",
                    "edge_cases": [
                        "Brak wymiarów → domyślne 2 inch",
                        "EMU conversion: /914400.0 * inch",
                        "Positioning relative_from (margin/page/rightMargin)"
                    ]
                }
            },
            
            "page_breaks": {
                "logic": "Sprawdź czy element mieści się na stronie",
                "conditions": [
                    "current_y + element_height > page_height - margin_bottom",
                    "Widows/orphans control dla numerowanych paragrafów",
                    "Page break w środku paragrafu → podziel linie"
                ],
                "edge_cases": [
                    "Paragraph z anchored images → sprawdź pozycję obrazu",
                    "Table za duża → może wymagać podziału",
                    "Footer overlap → dynamiczne margin_bottom"
                ]
            },
            
            "two_pass_rendering": {
                "pass_1": "_dry_run_render() - liczy strony",
                "pass_2": "Właściwe renderowanie z total_pages",
                "edge_cases": [
                    "Dry run musi być identyczny z właściwym renderowaniem",
                    "Cache musi być resetowany między passami",
                    "Page numbering w header/footer"
                ]
            },
            
            "coordinate_system": {
                "origin": "Bottom-left (ReportLab standard)",
                "y_direction": "Bottom to top (y increases upward)",
                "conversion": "DOCX top-to-bottom → ReportLab bottom-to-top",
                "edge_cases": [
                    "Anchored images: DOCX from top → ReportLab from bottom",
                    "Footer: bottom-to-top rendering",
                    "Header: top-to-bottom rendering"
                ]
            }
        }
        
        return analysis
    
    def analyze_layout_engine_logic(self) -> Dict[str, Any]:
        """Analizuje logikę obliczania w LayoutEngine."""
        
        analysis = {
            "page_setup": {
                "page_dimensions": {
                    "logic": "Hardcoded A4 = (595.28, 841.89)",
                    "edge_cases": [
                        "Brak obsługi innych rozmiarów",
                        "Brak ładowania z DOCX section properties"
                    ]
                },
                "margins": {
                    "default": "Hardcoded 72pt all around",
                    "docx_override": "NIE IMPLEMENTOWANE",
                    "dynamic_footer": "NIE IMPLEMENTOWANE",
                    "edge_cases": [
                        "Brak ładowania marginesów z DOCX",
                        "Brak dynamicznego obliczania footer height"
                    ]
                }
            },
            
            "positioning_logic": {
                "initial_position": {
                    "body": "current_y = 800.0 (hardcoded)",
                    "header": "calculated_y = 800.0 (hardcoded)",
                    "footer": "calculated_y = 50.0 (hardcoded)",
                    "edge_cases": [
                        "Brak uwzględnienia rzeczywistych marginesów",
                        "Brak konwersji DOCX coordinate system",
                        "Hardcoded wartości zamiast obliczeń"
                    ]
                },
                "element_positioning": {
                    "method": "current_y -= element_height",
                    "edge_cases": [
                        "Brak page break logic",
                        "Brak widows/orphans control",
                        "Brak anchored image positioning"
                    ]
                }
            },
            
            "height_calculation": {
                "paragraphs": {
                    "method": "Przybliżona: len(text) // 80 * 14.0",
                    "factors": [
                        "Tylko długość tekstu",
                        "Brak uwzględnienia font size",
                        "Brak uwzględnienia line spacing",
                        "Brak uwzględnienia space before/after"
                    ],
                    "edge_cases": [
                        "Bardzo niedokładne obliczenia",
                        "Brak obsługi empty paragraphs",
                        "Brak obsługi anchored images w paragraphs"
                    ]
                },
                "tables": {
                    "method": "rows * 20.0 (hardcoded)",
                    "edge_cases": [
                        "Brak uwzględnienia rzeczywistej wysokości komórek",
                        "Brak obsługi merged cells",
                        "Brak auto-fit width logic"
                    ]
                },
                "images": {
                    "method": "props.get('height', 100.0) (hardcoded)",
                    "edge_cases": [
                        "Brak konwersji EMU → points",
                        "Brak uwzględnienia rzeczywistych wymiarów",
                        "Brak obsługi positioning"
                    ]
                }
            },
            
            "page_breaks": {
                "logic": "NIE IMPLEMENTOWANE",
                "edge_cases": [
                    "Brak sprawdzania czy element mieści się na stronie",
                    "Brak page break logic",
                    "Brak pagination"
                ]
            },
            
            "two_pass_rendering": {
                "pass_1": "NIE IMPLEMENTOWANE",
                "pass_2": "Tylko jedno przejście",
                "edge_cases": [
                    "Brak liczenia stron",
                    "Brak page numbering",
                    "Brak dry run"
                ]
            },
            
            "coordinate_system": {
                "origin": "Top-left (niepoprawne dla ReportLab)",
                "y_direction": "Top to bottom (niepoprawne dla ReportLab)",
                "conversion": "BRAK KONWERSJI",
                "edge_cases": [
                    "Błędny coordinate system",
                    "Brak konwersji DOCX → ReportLab",
                    "Footer nie działa poprawnie"
                ]
            }
        }
        
        return analysis
    
    def identify_missing_logic(self) -> List[Dict[str, Any]]:
        """Identyfikuje brakującą logikę w LayoutEngine."""
        
        missing_logic = [
            {
                "category": "Page Setup",
                "issues": [
                    {
                        "issue": "Brak ładowania page size z DOCX",
                        "direct_pdf_logic": "document.section.properties.page_width/height",
                        "layout_engine_status": "BRAK",
                        "impact": "HIGH - błędne rozmiary stron"
                    },
                    {
                        "issue": "Brak ładowania marginesów z DOCX",
                        "direct_pdf_logic": "section_props.top_margin/bottom_margin/left_margin/right_margin",
                        "layout_engine_status": "BRAK",
                        "impact": "HIGH - błędne marginesy"
                    },
                    {
                        "issue": "Brak dynamicznego obliczania footer height",
                        "direct_pdf_logic": "_calculate_footer_height_dynamic()",
                        "layout_engine_status": "BRAK",
                        "impact": "HIGH - footer overlap"
                    }
                ]
            },
            
            {
                "category": "Positioning Logic",
                "issues": [
                    {
                        "issue": "Błędny coordinate system",
                        "direct_pdf_logic": "ReportLab bottom-left origin, y increases upward",
                        "layout_engine_status": "BŁĘDNY - top-left origin",
                        "impact": "CRITICAL - wszystko renderuje się błędnie"
                    },
                    {
                        "issue": "Brak page break logic",
                        "direct_pdf_logic": "Sprawdzenie czy element mieści się na stronie",
                        "layout_engine_status": "BRAK",
                        "impact": "HIGH - brak pagination"
                    },
                    {
                        "issue": "Brak anchored image positioning",
                        "direct_pdf_logic": "Absolutna pozycja niezależna od flow",
                        "layout_engine_status": "BRAK",
                        "impact": "MEDIUM - obrazy w złych pozycjach"
                    }
                ]
            },
            
            {
                "category": "Height Calculation",
                "issues": [
                    {
                        "issue": "Bardzo niedokładne obliczenia wysokości paragrafów",
                        "direct_pdf_logic": "TextBreaker.break_paragraph() + rzeczywiste line heights",
                        "layout_engine_status": "BARDZO NIEDOKŁADNE",
                        "impact": "HIGH - błędne pozycjonowanie"
                    },
                    {
                        "issue": "Brak uwzględnienia font size i line spacing",
                        "direct_pdf_logic": "font_size × line_spacing_multiplier",
                        "layout_engine_status": "BRAK",
                        "impact": "HIGH - błędne wysokości linii"
                    },
                    {
                        "issue": "Brak obsługi space before/after",
                        "direct_pdf_logic": "space_before + space_after w wysokości",
                        "layout_engine_status": "BRAK",
                        "impact": "MEDIUM - błędne odstępy"
                    }
                ]
            },
            
            {
                "category": "Edge Cases",
                "issues": [
                    {
                        "issue": "Brak obsługi empty paragraphs",
                        "direct_pdf_logic": "Minimalna wysokość dla empty paragraphs",
                        "layout_engine_status": "BRAK",
                        "impact": "MEDIUM - brak pustych linii"
                    },
                    {
                        "issue": "Brak obsługi widows/orphans control",
                        "direct_pdf_logic": "_numbered_continuation tracking",
                        "layout_engine_status": "BRAK",
                        "impact": "MEDIUM - złe łamanie numerowanych paragrafów"
                    },
                    {
                        "issue": "Brak obsługi merged cells w tabelach",
                        "direct_pdf_logic": "colspan/rowspan handling",
                        "layout_engine_status": "BRAK",
                        "impact": "MEDIUM - błędne tabele"
                    }
                ]
            },
            
            {
                "category": "Two-Pass Rendering",
                "issues": [
                    {
                        "issue": "Brak dry run dla liczenia stron",
                        "direct_pdf_logic": "_dry_run_render() przed właściwym renderowaniem",
                        "layout_engine_status": "BRAK",
                        "impact": "HIGH - brak page numbering"
                    },
                    {
                        "issue": "Brak cache management",
                        "direct_pdf_logic": "Reset cache między passami",
                        "layout_engine_status": "BRAK",
                        "impact": "MEDIUM - potencjalne błędy"
                    }
                ]
            }
        ]
        
        return missing_logic
    
    def generate_recommendations(self) -> List[Dict[str, Any]]:
        """Generuje rekomendacje dla poprawy LayoutEngine."""
        
        recommendations = [
            {
                "priority": "CRITICAL",
                "category": "Coordinate System",
                "action": "Popraw coordinate system na ReportLab standard",
                "details": [
                    "Zmień origin na bottom-left",
                    "Zmień y direction na bottom-to-top",
                    "Dodaj konwersję DOCX coordinates → ReportLab coordinates",
                    "Popraw footer positioning (od dołu strony)"
                ],
                "code_example": """
# Zamiast:
current_y = 800.0  # Top-down

# Użyj:
current_y = self.page_height - self.margin_top  # Bottom-up
                """
            },
            
            {
                "priority": "HIGH",
                "category": "Page Setup",
                "action": "Dodaj ładowanie page properties z DOCX",
                "details": [
                    "Ładuj page size z document.section.properties",
                    "Ładuj marginesy z section properties",
                    "Dodaj dynamiczne obliczanie footer height",
                    "Dodaj fallback values"
                ],
                "code_example": """
def _load_page_properties(self, document):
    if hasattr(document, 'section') and document.section:
        props = document.section.properties
        if props.page_width:
            self.page_width = self.twips_to_points(props.page_width)
        if props.top_margin:
            self.margin_top = self.twips_to_points(props.top_margin)
        # ... itd
                """
            },
            
            {
                "priority": "HIGH",
                "category": "Height Calculation",
                "action": "Zaimplementuj dokładne obliczanie wysokości",
                "details": [
                    "Użyj TextBreaker.break_paragraph() jak w direct_pdf_renderer",
                    "Uwzględnij font size × line_spacing_multiplier",
                    "Dodaj space before/after",
                    "Dodaj obsługę empty paragraphs"
                ],
                "code_example": """
def _calculate_paragraph_height(self, paragraph):
    # Użyj TextBreaker jak w direct_pdf_renderer
    lines = self.text_breaker.break_paragraph(paragraph, available_width, ...)
    total_height = sum(line.height for line in lines)
    
    # Dodaj spacing
    spacing = self._get_paragraph_spacing(paragraph)
    return total_height + spacing['before'] + spacing['after']
                """
            },
            
            {
                "priority": "HIGH",
                "category": "Page Breaks",
                "action": "Dodaj page break logic",
                "details": [
                    "Sprawdzaj czy element mieści się na stronie",
                    "Dodaj _new_page() logic",
                    "Dodaj widows/orphans control",
                    "Dodaj page numbering"
                ],
                "code_example": """
def _check_page_break(self, element_height):
    if self.current_y - element_height < self.margin_bottom:
        self._new_page()
        return True
    return False
                """
            },
            
            {
                "priority": "MEDIUM",
                "category": "Two-Pass Rendering",
                "action": "Dodaj two-pass rendering",
                "details": [
                    "Dodaj _dry_run_render() dla liczenia stron",
                    "Dodaj cache management",
                    "Dodaj page numbering w header/footer",
                    "Zapewnij identyczność między passami"
                ],
                "code_example": """
def process_document(self, document):
    # Pass 1: Dry run
    self.total_pages = self._dry_run_render(document)
    
    # Pass 2: Właściwe renderowanie
    self._reset_for_rendering()
    return self._render_document(document)
                """
            }
        ]
        
        return recommendations

def run_comparison_analysis():
    """Uruchamia pełną analizę porównawczą."""
    logger.info("Starting LayoutEngine vs DirectPDFRenderer comparison...")
    
    comparison = LayoutComparison()
    
    # Analizuj logikę
    direct_pdf_logic = comparison.analyze_direct_pdf_renderer_logic()
    layout_engine_logic = comparison.analyze_layout_engine_logic()
    
    # Identyfikuj brakującą logikę
    missing_logic = comparison.identify_missing_logic()
    
    # Generuj rekomendacje
    recommendations = comparison.generate_recommendations()
    
    # Wyświetl wyniki
    print("\n" + "="*80)
    print("ANALIZA PORÓWNAWCZA: LayoutEngine vs DirectPDFRenderer")
    print("="*80)
    
    print("\n🔍 BRAKUJĄCA LOGIKA W LAYOUTENGINE:")
    print("-" * 50)
    
    for category in missing_logic:
        print(f"\n📁 {category['category']}:")
        for issue in category['issues']:
            impact_emoji = {
                'CRITICAL': '🚨',
                'HIGH': '⚠️',
                'MEDIUM': '📝',
                'LOW': '💡'
            }.get(issue['impact'], '❓')
            
            print(f"  {impact_emoji} {issue['issue']}")
            print(f"     DirectPDF logic: {issue['direct_pdf_logic']}")
            print(f"     LayoutEngine: {issue['layout_engine_status']}")
            print(f"     Impact: {issue['impact']}")
    
    print("\n🎯 REKOMENDACJE:")
    print("-" * 50)
    
    for rec in recommendations:
        priority_emoji = {
            'CRITICAL': '🚨',
            'HIGH': '⚠️',
            'MEDIUM': '📝',
            'LOW': '💡'
        }.get(rec['priority'], '❓')
        
        print(f"\n{priority_emoji} {rec['priority']}: {rec['action']}")
        print(f"   Category: {rec['category']}")
        print("   Details:")
        for detail in rec['details']:
            print(f"     • {detail}")
        if 'code_example' in rec:
            print("   Code example:")
            print(rec['code_example'])
    
    print("\n" + "="*80)
    print("PODSUMOWANIE:")
    print("="*80)
    
    critical_count = sum(1 for rec in recommendations if rec['priority'] == 'CRITICAL')
    high_count = sum(1 for rec in recommendations if rec['priority'] == 'HIGH')
    medium_count = sum(1 for rec in recommendations if rec['priority'] == 'MEDIUM')
    
    print(f"🚨 CRITICAL issues: {critical_count}")
    print(f"⚠️ HIGH issues: {high_count}")
    print(f"📝 MEDIUM issues: {medium_count}")
    
    print(f"\n💡 LayoutEngine wymaga znaczących poprawek aby osiągnąć")
    print(f"   poziom jakości DirectPDFRenderer!")
    
    return {
        'direct_pdf_logic': direct_pdf_logic,
        'layout_engine_logic': layout_engine_logic,
        'missing_logic': missing_logic,
        'recommendations': recommendations
    }

if __name__ == "__main__":
    run_comparison_analysis()
