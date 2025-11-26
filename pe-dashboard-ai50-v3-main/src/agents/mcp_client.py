"""
MCP Client - HTTP client for calling MCP server tools
"""

import json
import requests
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for interacting with MCP server via HTTP"""
    
    def __init__(self, config_path: str = "config/mcp_config.json"):
        """Initialize MCP client with configuration"""
        
        # Load config
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"MCP config not found: {config_path}")
        
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        # Extract settings
        mcp_server = self.config.get("mcp_server", {})
        self.base_url = os.getenv('MCP_SERVER_URL') or mcp_server.get("base_url", "http://localhost:8100")
        self.timeout = mcp_server.get("timeout", 120)
        self.retry_attempts = mcp_server.get("retry_attempts", 3)
        self.retry_backoff_factor = mcp_server.get("retry_backoff_factor", 2)
        
        # Tool filtering
        tool_filtering = self.config.get("tool_filtering", {})
        self.filtering_enabled = tool_filtering.get("enabled", True)
        self.allowed_tools = tool_filtering.get("allowed_tools", [])
        self.blocked_tools = tool_filtering.get("blocked_tools", [])
        
        logger.info(f"MCP Client initialized with base_url: {self.base_url}")
    
    def _is_tool_allowed(self, tool_name: str) -> bool:
        """Check if tool is allowed by filtering rules"""
        if not self.filtering_enabled:
            return True
        
        # Check blocked list first
        if tool_name in self.blocked_tools:
            logger.warning(f"Tool '{tool_name}' is blocked")
            return False
        
        # Check allowed list
        if self.allowed_tools and tool_name not in self.allowed_tools:
            logger.warning(f"Tool '{tool_name}' is not in allowed list")
            return False
        
        return True
    
    def call_tool(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any],
        retry: bool = True
    ) -> Dict[str, Any]:
        """
        Call an MCP tool via HTTP
        
        Args:
            tool_name: Name of the tool (e.g., 'generate_structured_dashboard')
            parameters: Tool parameters as dict
            retry: Whether to retry on failure
        
        Returns:
            Tool response as dict
        """
        
        # Check if tool is allowed
        if not self._is_tool_allowed(tool_name):
            return {
                "success": False,
                "error": f"Tool '{tool_name}' is not allowed by filtering rules"
            }
        
        # Build URL
        url = f"{self.base_url}/tool/{tool_name}"
        
        # Attempt the request with retries
        attempts = self.retry_attempts if retry else 1
        
        for attempt in range(attempts):
            try:
                logger.info(f"Calling MCP tool: {tool_name} (attempt {attempt + 1}/{attempts})")
                
                response = requests.post(
                    url,
                    json=parameters,
                    timeout=self.timeout,
                    headers={"Content-Type": "application/json"}
                )
                
                # Check status
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Tool '{tool_name}' succeeded")
                    return result
                
                elif response.status_code == 404:
                    logger.error(f"Tool '{tool_name}' not found (404)")
                    return {
                        "success": False,
                        "error": f"Tool '{tool_name}' not found on MCP server"
                    }
                
                else:
                    logger.warning(f"Tool '{tool_name}' returned status {response.status_code}")
                    
                    # If not last attempt, retry
                    if attempt < attempts - 1:
                        import time
                        backoff_time = self.retry_backoff_factor ** attempt
                        logger.info(f"Retrying in {backoff_time}s...")
                        time.sleep(backoff_time)
                        continue
                    
                    # Last attempt failed
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }
            
            except requests.exceptions.Timeout:
                logger.error(f"Tool '{tool_name}' timed out after {self.timeout}s")
                
                if attempt < attempts - 1:
                    continue
                
                return {
                    "success": False,
                    "error": f"Request timed out after {self.timeout}s"
                }
            
            except requests.exceptions.ConnectionError:
                logger.error(f"Could not connect to MCP server at {self.base_url}")
                
                if attempt < attempts - 1:
                    continue
                
                return {
                    "success": False,
                    "error": f"Could not connect to MCP server at {self.base_url}"
                }
            
            except Exception as e:
                logger.error(f"Unexpected error calling tool '{tool_name}': {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        return {
            "success": False,
            "error": f"Failed after {attempts} attempts"
        }
    
    def get_resource(self, resource_path: str) -> Dict[str, Any]:
        """Get a resource from MCP server"""
        url = f"{self.base_url}/resource/{resource_path}"
        
        try:
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_prompt(self, prompt_id: str) -> Dict[str, Any]:
        """Get a prompt template from MCP server"""
        url = f"{self.base_url}/prompt/{prompt_id}"
        
        try:
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def discover(self) -> Dict[str, Any]:
        """Discover available tools, resources, and prompts"""
        url = f"{self.base_url}/mcp/discover"
        
        try:
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }