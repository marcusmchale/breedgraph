from typing import Type, get_type_hints
import inspect
from functools import wraps
import logging
logger = logging.getLogger(__name__)


class HandlerRegistry:
    def __init__(self):
        self.command_handlers = {}
        self.event_handlers = {}
        self.dependencies = {}

    def register_dependencies(self, **deps):
        """Register global dependencies"""
        self.dependencies.update(deps)

    def command_handler(self, command_type: Type = None):
        """Decorator for command handlers with auto dependency injection"""

        def decorator(func):
            # Auto-detect command type if not provided
            if command_type is None:
                type_hints = get_type_hints(func)
                detected_type = next(iter(type_hints.values()))
                actual_command_type = detected_type
            else:
                actual_command_type = command_type

            # Create dependency-injected wrapper
            injected_handler = self._inject_dependencies(func)
            self.command_handlers[actual_command_type] = injected_handler

            return func

        return decorator

    def event_handler(self, event_type: Type = None):
        """Decorator for event handlers with auto dependency injection"""

        def decorator(func):
            # Auto-detect event type if not provided
            if event_type is None:
                type_hints = get_type_hints(func)
                detected_type = next(iter(type_hints.values()))
                actual_event_type = detected_type
            else:
                actual_event_type = event_type

            # Create dependency-injected wrapper
            injected_handler = self._inject_dependencies(func)

            if actual_event_type not in self.event_handlers:
                self.event_handlers[actual_event_type] = []
            self.event_handlers[actual_event_type].append(injected_handler)

            return func

        return decorator

    def _inject_dependencies(self, handler_func):
        """Create dependency-injected version of handler"""
        type_hints = get_type_hints(handler_func)
        sig = inspect.signature(handler_func)

        # Find the message parameter (first parameter that's a Command or Event)
        message_param = None
        for param_name, param in sig.parameters.items():
            param_type = type_hints.get(param_name)
            if param_type and self._is_message_type(param_type):
                message_param = param_name
                break

        @wraps(handler_func)
        async def wrapper(message):
            kwargs = {}

            for param_name, param in sig.parameters.items():
                if param_name == message_param:
                    continue  # Skip the message parameter

                # Only inject dependencies that the handler expects
                if param_name in self.dependencies:
                    kwargs[param_name] = self.dependencies[param_name]
                elif param.default is not param.empty:
                    kwargs[param_name] = param.default

            return await handler_func(message, **kwargs)

        return wrapper

    def _is_message_type(self, param_type) -> bool:
        """Check if a type is a Command or Event"""
        if not hasattr(param_type, '__bases__'):
            return False

        # Check if it's a Command or Event
        for base in param_type.__mro__:
            if base.__name__ in ['Command', 'Event']:
                return True
        return False


# Create global registry
handlers = HandlerRegistry()