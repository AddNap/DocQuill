"""
Plugin system for DOCX interpreter.

Enables registration of custom parsers, models, and extensions.
"""

from typing import Dict, List, Any, Optional, Type, Callable, Union
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class Plugin(ABC):
    """
    Base plugin class for DOCX interpreter extensions.
    
    All plugins must inherit from this class.
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        """
        Initialize plugin.
        
        Args:
            name: Plugin name
            version: Plugin version
        """
        self.name = name
        self.version = version
        self.enabled = True
        
        logger.debug(f"Plugin {name} v{version} initialized")
    
    @abstractmethod
    def install(self, context: Dict[str, Any]) -> bool:
        """
        Install plugin.
        
        Args:
            context: Plugin context with available services
            
        Returns:
            True if installation successful, False otherwise
        """
        pass
    
    @abstractmethod
    def uninstall(self) -> bool:
        """
        Uninstall plugin.
        
        Returns:
            True if uninstallation successful, False otherwise
        """
        pass
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get plugin information.
        
        Returns:
            Plugin information dictionary
        """
        return {
            'name': self.name,
            'version': self.version,
            'enabled': self.enabled,
            'type': self.__class__.__name__
        }

class ParserPlugin(Plugin):
    """
    Plugin for custom XML parsers.
    
    Allows registration of custom parsers for specific XML tags.
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        super().__init__(name, version)
        self.parsers: Dict[str, Callable] = {}
    
    def register_parser(self, tag_name: str, parser_func: Callable):
        """
        Register parser for XML tag.
        
        Args:
            tag_name: XML tag name
            parser_func: Parser function
        """
        self.parsers[tag_name] = parser_func
        logger.debug(f"Registered parser for tag: {tag_name}")
    
    def get_parser(self, tag_name: str) -> Optional[Callable]:
        """
        Get parser for XML tag.
        
        Args:
            tag_name: XML tag name
            
        Returns:
            Parser function or None
        """
        return self.parsers.get(tag_name)
    
    def install(self, context: Dict[str, Any]) -> bool:
        """Install parser plugin."""
        try:
            xml_parser = context.get('xml_parser')
            if xml_parser:
                for tag_name, parser_func in self.parsers.items():
                    xml_parser.register_parser(tag_name, parser_func)
                logger.info(f"Parser plugin {self.name} installed successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to install parser plugin {self.name}: {e}")
        return False
    
    def uninstall(self) -> bool:
        """Uninstall parser plugin."""
        try:
            self.parsers.clear()
            logger.info(f"Parser plugin {self.name} uninstalled successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to uninstall parser plugin {self.name}: {e}")
            return False

class ModelPlugin(Plugin):
    """
    Plugin for custom model classes.
    
    Allows registration of custom model classes.
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        super().__init__(name, version)
        self.models: Dict[str, Type] = {}
    
    def register_model(self, model_name: str, model_class: Type):
        """
        Register model class.
        
        Args:
            model_name: Model name
            model_class: Model class
        """
        self.models[model_name] = model_class
        logger.debug(f"Registered model: {model_name}")
    
    def get_model(self, model_name: str) -> Optional[Type]:
        """
        Get model class.
        
        Args:
            model_name: Model name
            
        Returns:
            Model class or None
        """
        return self.models.get(model_name)
    
    def install(self, context: Dict[str, Any]) -> bool:
        """Install model plugin."""
        try:
            model_registry = context.get('model_registry')
            if model_registry:
                for model_name, model_class in self.models.items():
                    model_registry.register_model(model_name, model_class)
                logger.info(f"Model plugin {self.name} installed successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to install model plugin {self.name}: {e}")
        return False
    
    def uninstall(self) -> bool:
        """Uninstall model plugin."""
        try:
            self.models.clear()
            logger.info(f"Model plugin {self.name} uninstalled successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to uninstall model plugin {self.name}: {e}")
            return False

class RendererPlugin(Plugin):
    """
    Plugin for custom renderers.
    
    Allows registration of custom renderers for specific formats.
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        super().__init__(name, version)
        self.renderers: Dict[str, Type] = {}
    
    def register_renderer(self, format_name: str, renderer_class: Type):
        """
        Register renderer for format.
        
        Args:
            format_name: Format name
            renderer_class: Renderer class
        """
        self.renderers[format_name] = renderer_class
        logger.debug(f"Registered renderer for format: {format_name}")
    
    def get_renderer(self, format_name: str) -> Optional[Type]:
        """
        Get renderer for format.
        
        Args:
            format_name: Format name
            
        Returns:
            Renderer class or None
        """
        return self.renderers.get(format_name)
    
    def install(self, context: Dict[str, Any]) -> bool:
        """Install renderer plugin."""
        try:
            renderer_registry = context.get('renderer_registry')
            if renderer_registry:
                for format_name, renderer_class in self.renderers.items():
                    renderer_registry.register_renderer(format_name, renderer_class)
                logger.info(f"Renderer plugin {self.name} installed successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to install renderer plugin {self.name}: {e}")
        return False
    
    def uninstall(self) -> bool:
        """Uninstall renderer plugin."""
        try:
            self.renderers.clear()
            logger.info(f"Renderer plugin {self.name} uninstalled successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to uninstall renderer plugin {self.name}: {e}")
            return False

class HookSystem:
    """
    Hook system for event handling.
    
    Allows registration of hooks for various events.
    """
    
    def __init__(self):
        self.hooks: Dict[str, List[Callable]] = {}
        logger.debug("Hook system initialized")
    
    def register_hook(self, event_name: str, hook_func: Callable):
        """
        Register hook for event.
        
        Args:
            event_name: Event name
            hook_func: Hook function
        """
        if event_name not in self.hooks:
            self.hooks[event_name] = []
        self.hooks[event_name].append(hook_func)
        logger.debug(f"Registered hook for event: {event_name}")
    
    def unregister_hook(self, event_name: str, hook_func: Callable):
        """
        Unregister hook for event.
        
        Args:
            event_name: Event name
            hook_func: Hook function
        """
        if event_name in self.hooks:
            try:
                self.hooks[event_name].remove(hook_func)
                logger.debug(f"Unregistered hook for event: {event_name}")
            except ValueError:
                pass
    
    def trigger_hook(self, event_name: str, *args, **kwargs) -> List[Any]:
        """
        Trigger hooks for event.
        
        Args:
            event_name: Event name
            *args: Hook arguments
            **kwargs: Hook keyword arguments
            
        Returns:
            List of hook results
        """
        results = []
        if event_name in self.hooks:
            for hook_func in self.hooks[event_name]:
                try:
                    result = hook_func(*args, **kwargs)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Hook {hook_func.__name__} failed for event {event_name}: {e}")
        return results
    
    def get_hooks(self, event_name: str) -> List[Callable]:
        """
        Get hooks for event.
        
        Args:
            event_name: Event name
            
        Returns:
            List of hook functions
        """
        return self.hooks.get(event_name, [])

class PluginManager:
    """
    Plugin manager for DOCX interpreter.
    
    Manages plugin registration, installation, and lifecycle.
    """
    
    def __init__(self):
        self.plugins: Dict[str, Plugin] = {}
        self.hook_system = HookSystem()
        self.context: Dict[str, Any] = {}
        logger.debug("Plugin manager initialized")
    
    def register_plugin(self, plugin: Plugin) -> bool:
        """
        Register plugin.
        
        Args:
            plugin: Plugin instance
            
        Returns:
            True if registration successful, False otherwise
        """
        try:
            if plugin.name in self.plugins:
                logger.warning(f"Plugin {plugin.name} is already registered")
                return False
            
            self.plugins[plugin.name] = plugin
            logger.info(f"Plugin {plugin.name} registered successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to register plugin {plugin.name}: {e}")
            return False
    
    def unregister_plugin(self, plugin_name: str) -> bool:
        """
        Unregister plugin.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            True if unregistration successful, False otherwise
        """
        try:
            if plugin_name not in self.plugins:
                logger.warning(f"Plugin {plugin_name} is not registered")
                return False
            
            plugin = self.plugins[plugin_name]
            plugin.uninstall()
            del self.plugins[plugin_name]
            logger.info(f"Plugin {plugin_name} unregistered successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to unregister plugin {plugin_name}: {e}")
            return False
    
    def install_plugin(self, plugin_name: str) -> bool:
        """
        Install plugin.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            True if installation successful, False otherwise
        """
        try:
            if plugin_name not in self.plugins:
                logger.warning(f"Plugin {plugin_name} is not registered")
                return False
            
            plugin = self.plugins[plugin_name]
            success = plugin.install(self.context)
            if success:
                plugin.enabled = True
                logger.info(f"Plugin {plugin_name} installed successfully")
            return success
        except Exception as e:
            logger.error(f"Failed to install plugin {plugin_name}: {e}")
            return False
    
    def uninstall_plugin(self, plugin_name: str) -> bool:
        """
        Uninstall plugin.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            True if uninstallation successful, False otherwise
        """
        try:
            if plugin_name not in self.plugins:
                logger.warning(f"Plugin {plugin_name} is not registered")
                return False
            
            plugin = self.plugins[plugin_name]
            success = plugin.uninstall()
            if success:
                plugin.enabled = False
                logger.info(f"Plugin {plugin_name} uninstalled successfully")
            return success
        except Exception as e:
            logger.error(f"Failed to uninstall plugin {plugin_name}: {e}")
            return False
    
    def get_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """
        Get plugin by name.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            Plugin instance or None
        """
        return self.plugins.get(plugin_name)
    
    def get_plugins(self) -> Dict[str, Plugin]:
        """
        Get all plugins.
        
        Returns:
            Dictionary of plugins
        """
        return self.plugins.copy()
    
    def get_enabled_plugins(self) -> Dict[str, Plugin]:
        """
        Get enabled plugins.
        
        Returns:
            Dictionary of enabled plugins
        """
        return {name: plugin for name, plugin in self.plugins.items() if plugin.enabled}
    
    def set_context(self, context: Dict[str, Any]):
        """
        Set plugin context.
        
        Args:
            context: Plugin context
        """
        self.context.update(context)
        logger.debug("Plugin context updated")
    
    def get_hook_system(self) -> HookSystem:
        """
        Get hook system.
        
        Returns:
            Hook system instance
        """
        return self.hook_system
    
    def install_all_plugins(self) -> Dict[str, bool]:
        """
        Install all registered plugins.
        
        Returns:
            Dictionary of installation results
        """
        results = {}
        for plugin_name in self.plugins:
            results[plugin_name] = self.install_plugin(plugin_name)
        return results
    
    def uninstall_all_plugins(self) -> Dict[str, bool]:
        """
        Uninstall all plugins.
        
        Returns:
            Dictionary of uninstallation results
        """
        results = {}
        for plugin_name in self.plugins:
            results[plugin_name] = self.uninstall_plugin(plugin_name)
        return results
    
    def get_plugin_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all plugins.
        
        Returns:
            Dictionary of plugin information
        """
        return {name: plugin.get_info() for name, plugin in self.plugins.items()}
