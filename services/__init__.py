"""
HouseAI Services Module
========================

This module contains the core business logic services for the HouseAI application.

Services:
- enhanced_multi_agent_service: Enhanced multi-agent orchestration system with improved architecture
- list_services: Property wishlist management (add, get, delete)
- user_service: User authentication and JWT token management
- agents/: Multi-agent system components (search, analysis, chat, wishlist agents)

Usage:
    from services.enhanced_multi_agent_service import EnhancedMultiAgentOrchestrator
    from services.list_services import add_wish, get_wishlist, delete_wish
    from services.user_service import authenticate_user, create_access_token
    from services.agents import SearchAgent, ChatAgent, WishlistAgent
"""

# Core services exports
from .enhanced_multi_agent_service import (
    EnhancedMultiAgentOrchestrator,
    enhanced_websocket_chat_handler
)

from .list_services import (
    add_wish,
    get_wishlist,
    delete_wish
)

from .user_service import (
    authenticate_user,
    create_user,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_user,
    get_password_hash,
    verify_password
)

# Agent system exports
from .agents import (
    SearchAgent,
    ChatAgent,
    WishlistLAM,
    MultiAgentLogger,
    get_openai_client,
    multi_agent_logger
)

__all__ = [
    # Core services
    "EnhancedMultiAgentOrchestrator",
    "enhanced_websocket_chat_handler",
    
    # List services
    "add_wish",
    "get_wishlist", 
    "delete_wish",
    
    # User services
    "authenticate_user",
    "create_user",
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "get_current_user",
    "get_password_hash",
    "verify_password",
    
    # Agent system
    "SearchAgent",
    "ChatAgent",
    "WishlistLAM",
    "MultiAgentLogger",
    "get_openai_client",
    "multi_agent_logger"
]
