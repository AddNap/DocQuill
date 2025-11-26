#!/usr/bin/env python3
"""
Test runner script for docx_interpreter.

This script provides convenient ways to run different types of tests.
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: {cmd[0]}")
        return False


def run_unit_tests():
    """Run unit tests only."""
    cmd = ["python", "-m", "pytest", "tests/", "-m", "unit", "-v"]
    return run_command(cmd, "Unit Tests")


def run_integration_tests():
    """Run integration tests only."""
    cmd = ["python", "-m", "pytest", "tests/", "-m", "integration", "-v"]
    return run_command(cmd, "Integration Tests")


def run_all_tests():
    """Run all tests."""
    cmd = ["python", "-m", "pytest", "tests/", "-v"]
    return run_command(cmd, "All Tests")


def run_parser_tests():
    """Run parser tests only."""
    cmd = ["python", "-m", "pytest", "tests/parsers/", "-v"]
    return run_command(cmd, "Parser Tests")


def run_renderer_tests():
    """Run renderer tests only."""
    cmd = ["python", "-m", "pytest", "tests/renderers/", "-v"]
    return run_command(cmd, "Renderer Tests")


def run_layout_tests():
    """Run layout tests only."""
    cmd = ["python", "-m", "pytest", "tests/engines/", "-v"]
    return run_command(cmd, "Layout Tests")


def run_performance_tests():
    """Run performance tests."""
    cmd = ["python", "-m", "pytest", "tests/", "-m", "performance", "-v", "--durations=10"]
    return run_command(cmd, "Performance Tests")


def run_with_coverage():
    """Run tests with coverage report."""
    cmd = [
        "python", "-m", "pytest", "tests/", 
        "--cov=docx_interpreter", 
        "--cov-report=html", 
        "--cov-report=term-missing",
        "-v"
    ]
    return run_command(cmd, "Tests with Coverage")


def run_parallel_tests():
    """Run tests in parallel."""
    cmd = ["python", "-m", "pytest", "tests/", "-n", "auto", "-v"]
    return run_command(cmd, "Parallel Tests")


def run_specific_test(test_path):
    """Run a specific test file or test function."""
    cmd = ["python", "-m", "pytest", test_path, "-v"]
    return run_command(cmd, f"Specific Test: {test_path}")


def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = [
        "pytest",
        "pytest-cov",
        "pytest-mock",
        "psutil"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing required packages: {', '.join(missing_packages)}")
        print("Install them with: pip install -r tests/requirements.txt")
        return False
    
    print("✅ All required packages are installed")
    return True


def main():
    """Main function to run tests based on command line arguments."""
    parser = argparse.ArgumentParser(description="Run docx_interpreter tests")
    parser.add_argument(
        "test_type", 
        nargs="?", 
        default="all",
        choices=[
            "all", "unit", "integration", "parser", "renderer", 
            "layout", "performance", "coverage", "parallel", "check"
        ],
        help="Type of tests to run"
    )
    parser.add_argument(
        "--test-path", 
        help="Specific test file or function to run"
    )
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true", 
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # Change to the project root directory
    project_root = Path(__file__).parent.parent
    import os
    os.chdir(project_root)
    
    print(f"Running tests from: {project_root}")
    print(f"Python version: {sys.version}")
    
    success = True
    
    if args.test_type == "check":
        success = check_dependencies()
    elif args.test_type == "all":
        success = run_all_tests()
    elif args.test_type == "unit":
        success = run_unit_tests()
    elif args.test_type == "integration":
        success = run_integration_tests()
    elif args.test_type == "parser":
        success = run_parser_tests()
    elif args.test_type == "renderer":
        success = run_renderer_tests()
    elif args.test_type == "layout":
        success = run_layout_tests()
    elif args.test_type == "performance":
        success = run_performance_tests()
    elif args.test_type == "coverage":
        success = run_with_coverage()
    elif args.test_type == "parallel":
        success = run_parallel_tests()
    
    if args.test_path:
        success = run_specific_test(args.test_path)
    
    if success:
        print(f"\n🎉 All tests completed successfully!")
        sys.exit(0)
    else:
        print(f"\n💥 Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
