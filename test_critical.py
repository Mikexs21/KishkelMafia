"""
Critical configuration and dependency testing for Mafia Bot.
Run this before deploying to production.
"""

import sys
import os
from pathlib import Path
from typing import List, Tuple

# Color codes for terminal output
class Colors:
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_section(title: str) -> None:
    """Print section header."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{title}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.RESET}\n")

def print_success(message: str) -> None:
    """Print success message."""
    print(f"{Colors.GREEN}✅ {message}{Colors.RESET}")

def print_error(message: str) -> None:
    """Print error message."""
    print(f"{Colors.RED}❌ {message}{Colors.RESET}")

def print_warning(message: str) -> None:
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.RESET}")

def print_info(message: str) -> None:
    """Print info message."""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.RESET}")


def test_dependencies() -> Tuple[bool, List[str]]:
    """Test if all required dependencies are installed."""
    print_section("Testing Dependencies")
    errors = []
    
    # Required packages
    required = [
        ("telegram", "python-telegram-bot"),
        ("aiosqlite", "aiosqlite"),
    ]
    
    for module_name, package_name in required:
        try:
            __import__(module_name)
            print_success(f"{package_name} installed")
        except ImportError:
            error = f"{package_name} not installed. Run: pip install {package_name}"
            print_error(error)
            errors.append(error)
    
    # Check telegram version
    try:
        import telegram
        version = telegram.__version__
        major = int(version.split('.')[0])
        if major < 20:
            error = f"python-telegram-bot version {version} is too old. Need >= 20.0"
            print_error(error)
            errors.append(error)
        else:
            print_success(f"python-telegram-bot version {version}")
    except Exception as e:
        error = f"Failed to check telegram version: {e}"
        print_error(error)
        errors.append(error)
    
    return len(errors) == 0, errors


def test_config() -> Tuple[bool, List[str]]:
    """Test configuration file."""
    print_section("Testing Configuration")
    errors = []
    
    try:
        import config
        print_success("config.py imports successfully")
    except Exception as e:
        error = f"Failed to import config.py: {e}"
        print_error(error)
        errors.append(error)
        return False, errors
    
    # Critical settings
    critical_checks = [
        ("BOT_TOKEN", str, lambda x: x != "PASTE_TOKEN_HERE"),
        ("DATABASE_FILE", str, None),
        ("ROLE_DISTRIBUTION", dict, None),
        ("MIN_PLAYERS", int, lambda x: 4 <= x <= 15),
        ("MAX_PLAYERS", int, lambda x: x >= config.MIN_PLAYERS),
        ("SHOP_ITEMS", dict, None),
    ]
    
    for name, expected_type, validator in critical_checks:
        if not hasattr(config, name):
            error = f"{name} not found in config.py"
            print_error(error)
            errors.append(error)
            continue
        
        value = getattr(config, name)
        
        if not isinstance(value, expected_type):
            error = f"{name} must be {expected_type.__name__}, got {type(value).__name__}"
            print_error(error)
            errors.append(error)
            continue
        
        if validator and not validator(value):
            error = f"{name} validation failed: {value}"
            print_error(error)
            errors.append(error)
            continue
        
        print_success(f"{name}: {repr(value)[:50]}")
    
    # Validate role distribution
    if hasattr(config, 'ROLE_DISTRIBUTION'):
        for player_count, roles in config.ROLE_DISTRIBUTION.items():
            if len(roles) != player_count:
                error = f"ROLE_DISTRIBUTION[{player_count}]: has {len(roles)} roles, expected {player_count}"
                print_error(error)
                errors.append(error)
            
            # Check for mafia
            mafia_count = sum(1 for r in roles if r in ["don", "mafia", "consigliere"])
            if mafia_count == 0:
                error = f"ROLE_DISTRIBUTION[{player_count}]: no mafia roles"
                print_error(error)
                errors.append(error)
            
            # Check for civilians
            civilian_count = sum(1 for r in roles if r not in ["don", "mafia", "consigliere"])
            if civilian_count == 0:
                error = f"ROLE_DISTRIBUTION[{player_count}]: no civilian roles"
                print_error(error)
                errors.append(error)
        
        print_success(f"ROLE_DISTRIBUTION validated for {len(config.ROLE_DISTRIBUTION)} player counts")
    
    # Use config's validation if available
    if hasattr(config, 'validate_config'):
        is_valid, config_errors = config.validate_config()
        if not is_valid:
            for error in config_errors:
                print_error(error)
                errors.append(error)
        else:
            print_success("config.validate_config() passed")
    
    return len(errors) == 0, errors


def test_files() -> Tuple[bool, List[str]]:
    """Test required files exist."""
    print_section("Testing Files")
    errors = []
    warnings = []
    
    # Required Python files
    required_files = [
        "main.py",
        "engine.py",
        "config.py",
        "db.py",
        "bot_ai.py",
        "visual.py",
    ]
    
    for filename in required_files:
        if Path(filename).exists():
            print_success(f"{filename} exists")
        else:
            error = f"{filename} not found"
            print_error(error)
            errors.append(error)
    
    # Optional but recommended files
    optional_files = [
        ("requirements.txt", "Dependency list"),
        ("README.md", "Documentation"),
        (".gitignore", "Git ignore rules"),
    ]
    
    for filename, description in optional_files:
        if Path(filename).exists():
            print_success(f"{filename} exists ({description})")
        else:
            warning = f"{filename} not found ({description})"
            print_warning(warning)
            warnings.append(warning)
    
    # GIF files
    gif_dir = Path("gifs")
    if gif_dir.exists():
        print_success("gifs/ directory exists")
        
        required_gifs = [
            "night.gif",
            "morning.gif",
            "vote.gif",
            "dead.gif",
            "lost_civil.gif",
            "lost_mafia.gif",
        ]
        
        for gif in required_gifs:
            if (gif_dir / gif).exists():
                print_success(f"  {gif} exists")
            else:
                warning = f"{gif} not found (will use text fallback)"
                print_warning(warning)
                warnings.append(warning)
    else:
        warning = "gifs/ directory not found (will use text fallbacks)"
        print_warning(warning)
        warnings.append(warning)
    
    # Logs directory
    logs_dir = Path("logs")
    if logs_dir.exists():
        print_success("logs/ directory exists")
    else:
        print_info("logs/ directory will be created on startup")
    
    return len(errors) == 0, errors + warnings


def test_database() -> Tuple[bool, List[str]]:
    """Test database functionality."""
    print_section("Testing Database")
    errors = []
    
    try:
        import asyncio
        import db
        
        async def test_db_operations():
            # Initialize
            await db.init_db()
            print_success("Database initialized")
            
            # Test user creation
            user_id = await db.get_or_create_user(12345, "test_user")
            print_success(f"User created with ID: {user_id}")
            
            # Test user retrieval
            user_data = await db.get_user_by_telegram_id(12345)
            if user_data:
                print_success("User retrieved successfully")
            else:
                errors.append("Failed to retrieve user")
                print_error("Failed to retrieve user")
            
            # Test points update
            await db.update_user_points(user_id, 10)
            print_success("Points updated")
            
            # Test stats update
            await db.update_user_stats(user_id, total_games=1, wins=1)
            print_success("Stats updated")
            
            # Clean up
            await db.close_db()
            print_success("Database closed")
            
            # Remove test DB
            import config
            test_db_path = Path(config.DATABASE_FILE)
            if test_db_path.exists():
                test_db_path.unlink()
                print_success("Test database cleaned up")
        
        asyncio.run(test_db_operations())
        
    except Exception as e:
        error = f"Database test failed: {e}"
        print_error(error)
        errors.append(error)
    
    return len(errors) == 0, errors


def test_bot_ai() -> Tuple[bool, List[str]]:
    """Test bot AI imports and basic functionality."""
    print_section("Testing Bot AI")
    errors = []
    
    try:
        from bot_ai import bot_ai, BotAI, SuspicionLevel
        print_success("bot_ai imports successfully")
        
        # Test basic AI instance
        if bot_ai and isinstance(bot_ai, BotAI):
            print_success("Global bot_ai instance exists")
        else:
            error = "bot_ai instance is invalid"
            print_error(error)
            errors.append(error)
        
        # Test SuspicionLevel enum
        if len(SuspicionLevel) >= 5:
            print_success(f"SuspicionLevel has {len(SuspicionLevel)} levels")
        else:
            error = f"SuspicionLevel should have 5 levels, got {len(SuspicionLevel)}"
            print_error(error)
            errors.append(error)
        
    except Exception as e:
        error = f"Bot AI test failed: {e}"
        print_error(error)
        errors.append(error)
    
    return len(errors) == 0, errors


def test_visual() -> Tuple[bool, List[str]]:
    """Test visual module."""
    print_section("Testing Visual Module")
    errors = []
    
    try:
        import visual
        print_success("visual.py imports successfully")
        
        # Test required constants
        required = [
            "ROLE_NAMES",
            "ROLE_DESCRIPTIONS",
            "BOT_NAMES",
            "EVENT_MESSAGES",
        ]
        
        for const in required:
            if hasattr(visual, const):
                value = getattr(visual, const)
                print_success(f"{const}: {len(value)} entries")
            else:
                error = f"{const} not found in visual.py"
                print_error(error)
                errors.append(error)
        
        # Test functions exist
        required_functions = [
            "format_lobby_message",
            "format_morning_report",
            "format_profile",
            "get_lobby_keyboard",
        ]
        
        for func_name in required_functions:
            if hasattr(visual, func_name):
                print_success(f"{func_name}() exists")
            else:
                error = f"{func_name}() not found in visual.py"
                print_error(error)
                errors.append(error)
        
    except Exception as e:
        error = f"Visual module test failed: {e}"
        print_error(error)
        errors.append(error)
    
    return len(errors) == 0, errors


def print_summary(all_results: dict) -> None:
    """Print test summary."""
    print_section("Test Summary")
    
    total_errors = []
    total_warnings = []
    
    for test_name, (passed, issues) in all_results.items():
        if passed:
            print_success(f"{test_name}: PASSED")
        else:
            print_error(f"{test_name}: FAILED")
            total_errors.extend(issues)
    
    print()
    
    if total_errors:
        print(f"{Colors.RED}{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"{Colors.RED}{Colors.BOLD}❌ CRITICAL ERRORS FOUND: {len(total_errors)}{Colors.RESET}")
        print(f"{Colors.RED}{Colors.BOLD}{'='*60}{Colors.RESET}\n")
        for error in total_errors:
            print(f"{Colors.RED}  • {error}{Colors.RESET}")
        print(f"\n{Colors.RED}⛔ Fix these errors before running the bot!{Colors.RESET}\n")
        return False
    else:
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"{Colors.GREEN}{Colors.BOLD}✅ ALL TESTS PASSED!{Colors.RESET}")
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*60}{Colors.RESET}\n")
        print(f"{Colors.GREEN}🚀 Bot is ready to start!{Colors.RESET}\n")
        return True


def main():
    """Run all tests."""
    print(f"\n{Colors.MAGENTA}{Colors.BOLD}{'='*60}")
    print("🧪 Mafia Bot - Critical Tests")
    print(f"{'='*60}{Colors.RESET}\n")
    
    results = {}
    
    # Run tests
    results["Dependencies"] = test_dependencies()
    results["Configuration"] = test_config()
    results["Files"] = test_files()
    results["Database"] = test_database()
    results["Bot AI"] = test_bot_ai()
    results["Visual"] = test_visual()
    
    # Print summary
    all_passed = print_summary(results)
    
    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()