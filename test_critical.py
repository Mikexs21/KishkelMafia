import config
import sys

def test_critical_configs():
    '''Перевірити критичні налаштування перед запуском.'''
    
    errors = []
    warnings = []
    
    # Критичні перевірки
    if not hasattr(config, 'DATABASE_FILE'):
        errors.append("DATABASE_FILE not found in config.py")
    
    if not hasattr(config, 'ROLE_DISTRIBUTION'):
        errors.append("ROLE_DISTRIBUTION not found in config.py")
    
    if not hasattr(config, 'BOT_TOKEN') or config.BOT_TOKEN == "PASTE_TOKEN_HERE":
        errors.append("BOT_TOKEN not configured in config.py")
    
    # Попередження
    if not hasattr(config, 'ALLOW_PETRUSHKA'):
        warnings.append("ALLOW_PETRUSHKA not found (will default to False)")
    
    # Виведення результатів
    if errors:
        print("❌ CRITICAL ERRORS:")
        for err in errors:
            print(f"   - {err}")
        print("\n⛔ Cannot start bot until these are fixed!")
        sys.exit(1)
    
    if warnings:
        print("⚠️  WARNINGS:")
        for warn in warnings:
            print(f"   - {warn}")
    
    print("✅ All critical checks passed!")
    return True

if __name__ == "__main__":
    test_critical_configs()
"""