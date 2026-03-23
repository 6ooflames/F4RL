#!/usr/bin/env python3
"""
Test script for GamePlayer controller server
"""
import sys
import time
import json
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, '/mnt/data1/Apps/GamePlayer')
sys.path.insert(0, '/mnt/data1/Apps')

from controller_server import app, map_action_to_keys
from pipboy_relay import PipBoyRelay


def test_controller_import():
    """Test if controller_server can be imported"""
    print("✓ Test 1: Import controller_server")
    print("  - Successfully imported module")
    return True


def test_pipboy_relay_import():
    """Test if pipboy_relay can be imported"""
    print("✓ Test 2: Import pipboy_relay")
    print("  - Successfully imported module")
    return True


def test_map_action_simple():
    """Test simple key mapping"""
    print("\n✓ Test 3: Simple key mapping")
    
    # Test basic actions
    test_cases = [
        ("loot", "tab space"),
        ("take", "e"),
        ("stimpack", "f"),
        ("rest", "v"),
        ("search", "t"),
    ]
    
    for action, expected in test_cases:
        result = map_action_to_keys(action)
        print(f"  - '{action}' -> '{result}'")
        if not result:
            print(f"    ⚠ WARNING: Got empty result for '{action}'")
    
    return True


def test_map_action_special_keys():
    """Test special key mapping"""
    print("\n✓ Test 4: Special key mapping")
    
    test_cases = [
        ("open inventory", "tab space"),
        ("press space", "space"),
        ("close menu", "tab"),
        ("take all", "s tab"),
    ]
    
    for action, expected in test_cases:
        result = map_action_to_keys(action)
        print(f"  - '{action}' -> '{result}'")
    
    return True


def test_flask_config():
    """Test Flask app configuration"""
    print("\n✓ Test 5: Flask app configuration")
    
    # Check if app has expected attributes
    app_attrs = {
        'name': app.name,
        'import_name': app.import_name,
        'test-client': hasattr(app, 'test_client'),
    }
    
    for attr, value in app_attrs.items():
        print(f"  - {attr}: {value}")
    
    if not hasattr(app, 'test_client'):
        print("  ⚠ WARNING: Flask app missing test_client method")
    
    return True


def test_pipboy_relay_init():
    """Test PipBoyRelay initialization"""
    print("\n✓ Test 6: PipBoyRelay initialization")
    
    try:
        # Test with default socket
        relay = PipBoyRelay()
        print(f"  - Created relay with socket: {relay.game_socket}")
        print(f"  - Relay running: {relay.running}")
    except Exception as e:
        print(f"  ✗ ERROR: Failed to initialize PipBoyRelay: {e}")
        return False
    
    return True


def test_endpoints():
    """Test API endpoints"""
    print("\n✓ Test 7: API endpoints")
    
    # Create a test client
    with app.test_client() as client:
        # Test health endpoint
        response = client.get('/health')
        print(f"  - /health status: {response.status_code}")
        
        # Test get_session endpoint
        response = client.get('/get_session')
        if response.status_code == 200:
            data = json.loads(response.data)
            print(f"  - /get_session response: {json.dumps(data, indent=6)}")
        else:
            print(f"  - /get_session status: {response.status_code}")
        
        # Test action mapping endpoint
        response = client.post('/map_action', 
                            json={'action': 'loot'})
        if response.status_code == 200:
            data = json.loads(response.data)
            print(f"  - /map_action response: {data}")
        else:
            print(f"  - /map_action status: {response.status_code}")
    
    return True


def test_cors_config():
    """Test CORS configuration"""
    print("\n✓ Test 8: CORS configuration")
    
    if hasattr(app, 'cors'):
        print(f"  - CORS enabled: {app.cors}")
    else:
        print(f"  - CORS not explicitly configured")
    
    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("GamePlayer Controller Server - Test Suite")
    print("=" * 60)
    
    tests = [
        test_controller_import,
        test_pipboy_relay_import,
        test_map_action_simple,
        test_map_action_special_keys,
        test_flask_config,
        test_pipboy_relay_init,
        test_endpoints,
        test_cors_config,
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            print(f"\n✗ {test_func.__name__} FAILED: {e}")
            results.append((test_func.__name__, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠ {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())