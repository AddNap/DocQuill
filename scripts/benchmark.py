#!/usr/bin/env python3
"""
Benchmark script for DOCX interpreter performance.

Measures parsing and rendering performance across different document types.
"""

import sys
import os
import time
import psutil
import gc
from pathlib import Path
from typing import Dict, List, Any, Optional
import argparse

# Add project root to path (scripts/ is in project root)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from docquill import Document
from docquill.renderers import HTMLRenderer, PDFRenderer, DOCXRenderer

class BenchmarkResults:
    """Container for benchmark results."""
    
    def __init__(self):
        self.results: Dict[str, Dict[str, Any]] = {}
    
    def add_result(self, test_name: str, operation: str, duration: float, 
                   memory_usage: float, success: bool, details: Optional[Dict[str, Any]] = None):
        """Add benchmark result."""
        if test_name not in self.results:
            self.results[test_name] = {}
        
        self.results[test_name][operation] = {
            'duration': duration,
            'memory_usage': memory_usage,
            'success': success,
            'details': details or {}
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get benchmark summary."""
        summary = {
            'total_tests': len(self.results),
            'total_operations': sum(len(ops) for ops in self.results.values()),
            'successful_operations': 0,
            'failed_operations': 0,
            'total_duration': 0.0,
            'total_memory': 0.0
        }
        
        for test_results in self.results.values():
            for operation_result in test_results.values():
                if operation_result['success']:
                    summary['successful_operations'] += 1
                else:
                    summary['failed_operations'] += 1
                
                summary['total_duration'] += operation_result['duration']
                summary['total_memory'] += operation_result['memory_usage']
        
        return summary
    
    def print_report(self):
        """Print benchmark report."""
        print("=" * 80)
        print("DOCX INTERPRETER BENCHMARK REPORT")
        print("=" * 80)
        
        summary = self.get_summary()
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Total Operations: {summary['total_operations']}")
        print(f"Successful: {summary['successful_operations']}")
        print(f"Failed: {summary['failed_operations']}")
        print(f"Total Duration: {summary['total_duration']:.2f}s")
        print(f"Total Memory: {summary['total_memory']:.2f}MB")
        print()
        
        for test_name, test_results in self.results.items():
            print(f"Test: {test_name}")
            print("-" * 40)
            
            for operation, result in test_results.items():
                status = "✓" if result['success'] else "✗"
                print(f"  {status} {operation}: {result['duration']:.3f}s, {result['memory_usage']:.2f}MB")
                
                if result['details']:
                    for key, value in result['details'].items():
                        print(f"    {key}: {value}")
            
            print()

def measure_memory_usage():
    """Measure current memory usage in MB."""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024

def benchmark_operation(func, *args, **kwargs):
    """Benchmark a single operation."""
    gc.collect()  # Clean up before measurement
    
    start_memory = measure_memory_usage()
    start_time = time.time()
    
    try:
        result = func(*args, **kwargs)
        success = True
    except Exception as e:
        result = None
        success = False
        error = str(e)
    
    end_time = time.time()
    end_memory = measure_memory_usage()
    
    duration = end_time - start_time
    memory_usage = end_memory - start_memory
    
    details = {}
    if not success:
        details['error'] = error
    elif result is not None:
        if hasattr(result, '__len__'):
            details['result_size'] = len(result)
        if hasattr(result, 'get_text'):
            details['text_length'] = len(result.get_text())
    
    return duration, memory_usage, success, details

def benchmark_document_parsing(docx_path: str, results: BenchmarkResults):
    """Benchmark document parsing."""
    test_name = f"parsing_{Path(docx_path).stem}"
    
    # Benchmark full parsing
    def parse_document():
        doc = Document.from_file(docx_path)
        return doc
    
    duration, memory, success, details = benchmark_operation(parse_document)
    results.add_result(test_name, "full_parsing", duration, memory, success, details)
    
    if success:
        # Benchmark modular parsing
        def parse_metadata_only():
            doc = Document.from_file(docx_path)
            doc.parse(components=["metadata"])
            return doc
        
        duration, memory, success, details = benchmark_operation(parse_metadata_only)
        results.add_result(test_name, "metadata_only", duration, memory, success, details)
        
        def parse_body_only():
            doc = Document.from_file(docx_path)
            doc.parse(components=["body"])
            return doc
        
        duration, memory, success, details = benchmark_operation(parse_body_only)
        results.add_result(test_name, "body_only", duration, memory, success, details)

def benchmark_document_rendering(docx_path: str, results: BenchmarkResults):
    """Benchmark document rendering."""
    test_name = f"rendering_{Path(docx_path).stem}"
    
    try:
        doc = Document.from_file(docx_path)
    except Exception:
        results.add_result(test_name, "html_render", 0, 0, False, {"error": "Failed to parse document"})
        return
    
    # Benchmark HTML rendering
    def render_html():
        renderer = HTMLRenderer(doc)
        return renderer.render()
    
    duration, memory, success, details = benchmark_operation(render_html)
    results.add_result(test_name, "html_render", duration, memory, success, details)
    
    # Benchmark PDF rendering
    def render_pdf():
        renderer = PDFRenderer(doc)
        return renderer.render()
    
    duration, memory, success, details = benchmark_operation(render_pdf)
    results.add_result(test_name, "pdf_render", duration, memory, success, details)
    
    # Benchmark DOCX diagnostic rendering
    def render_docx():
        renderer = DOCXRenderer(doc)
        return renderer.render()
    
    duration, memory, success, details = benchmark_operation(render_docx)
    results.add_result(test_name, "docx_diagnostic_render", duration, memory, success, details)

def benchmark_document_operations(docx_path: str, results: BenchmarkResults):
    """Benchmark document operations."""
    test_name = f"operations_{Path(docx_path).stem}"
    
    try:
        doc = Document.from_file(docx_path)
    except Exception:
        results.add_result(test_name, "get_text", 0, 0, False, {"error": "Failed to parse document"})
        return
    
    # Benchmark text extraction
    def get_text():
        return doc.get_text()
    
    duration, memory, success, details = benchmark_operation(get_text)
    results.add_result(test_name, "get_text", duration, memory, success, details)
    
    # Benchmark paragraph extraction
    def get_paragraphs():
        return doc.get_paragraphs()
    
    duration, memory, success, details = benchmark_operation(get_paragraphs)
    results.add_result(test_name, "get_paragraphs", duration, memory, success, details)
    
    # Benchmark table extraction
    def get_tables():
        return doc.get_tables()
    
    duration, memory, success, details = benchmark_operation(get_tables)
    results.add_result(test_name, "get_tables", duration, memory, success, details)
    
    # Benchmark image extraction
    def get_images():
        return doc.get_images()
    
    duration, memory, success, details = benchmark_operation(get_images)
    results.add_result(test_name, "get_images", duration, memory, success, details)

def benchmark_validation(docx_path: str, results: BenchmarkResults):
    """Benchmark document validation."""
    test_name = f"validation_{Path(docx_path).stem}"
    
    try:
        doc = Document.from_file(docx_path)
    except Exception:
        results.add_result(test_name, "validate", 0, 0, False, {"error": "Failed to parse document"})
        return
    
    # Benchmark validation
    def validate_document():
        return doc.validate()
    
    duration, memory, success, details = benchmark_operation(validate_document)
    results.add_result(test_name, "validate", duration, memory, success, details)

def main():
    """Main benchmark function."""
    parser = argparse.ArgumentParser(description="Benchmark DOCX interpreter performance")
    parser.add_argument("--docx-path", default="tests/files/Zapytanie_Ofertowe.docx", 
                       help="Path to DOCX file for benchmarking")
    parser.add_argument("--output", help="Output file for benchmark results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if not Path(args.docx_path).exists():
        print(f"Error: DOCX file not found: {args.docx_path}")
        return 1
    
    print("Starting DOCX Interpreter Benchmark...")
    print(f"Document: {args.docx_path}")
    print()
    
    results = BenchmarkResults()
    
    # Run benchmarks
    benchmark_document_parsing(args.docx_path, results)
    benchmark_document_rendering(args.docx_path, results)
    benchmark_document_operations(args.docx_path, results)
    benchmark_validation(args.docx_path, results)
    
    # Print results
    results.print_report()
    
    # Save results if requested
    if args.output:
        import json
        with open(args.output, 'w') as f:
            json.dump(results.results, f, indent=2)
        print(f"Results saved to: {args.output}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
