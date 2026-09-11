#!/usr/bin/env python3
"""
Test script to verify Phase 0 works correctly.
"""

import sys
import os
import subprocess

# Add the src directory to Python path for importing passist modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_import():
    """Test that we can import passist"""
    try:
        import passist
        print("✓ passist package imports correctly")
        return True
    except Exception as e:
        print(f"✗ Failed to import passist: {e}")
        return False

def test_registry_import():
    """Test that we can import the registry"""
    try:
        from passist.api.registry import TOOLS, TOOLS_BY_NAME
        print("✓ Registry imports correctly")
        print(f"  Found {len(TOOLS)} tools in registry")
        for tool in TOOLS:
            print(f"  - {tool['name']}: {tool['description']}")
        return True
    except Exception as e:
        print(f"✗ Failed to import registry: {e}")
        return False

def test_tools_import():
    """Test that we can import individual tools"""
    try:
        from passist.api.tools.get_thing import spec as get_thing_spec
        from passist.api.tools.update_thing import spec as update_thing_spec
        
        print("✓ Tool modules import correctly")
        
        # Print tool info
        print(f"  Get Thing: {get_thing_spec['name']} ({'Write' if get_thing_spec['side_effect'] else 'Read'})")
        print(f"  Update Thing: {update_thing_spec['name']} ({'Write' if update_thing_spec['side_effect'] else 'Read'})")
        
        return True
    except Exception as e:
        print(f"✗ Failed to import tools: {e}")
        return False

def test_direct_imports():
    """Test direct imports of CLI modules"""
    try:
        from passist.api import cli
        from passist.api import run
        
        print("✓ CLI modules import correctly")
        return True
    except Exception as e:
        print(f"✗ Failed to import CLI modules: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing Phase 0 - Skeleton Setup")
    print("=" * 40)
    
    tests = [
        test_import,
        test_registry_import, 
        test_tools_import,
        test_direct_imports
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ Phase 0 setup completed successfully!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())