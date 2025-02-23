#!/usr/bin/env python3
"""Script to run all tests with coverage reporting"""
import pytest
import sys

if __name__ == '__main__':
    # Add current directory to Python path
    sys.path.append('.')
    
    # Run tests with coverage
    exit_code = pytest.main([
        '-v',  # Verbose output
        '--cov=.',  # Coverage for all files
        '--cov-report=term-missing',  # Show lines missing coverage
        '--cov-report=html:coverage_report',  # Generate HTML coverage report
        'tests'  # Test directory
    ])
    
    sys.exit(exit_code) 