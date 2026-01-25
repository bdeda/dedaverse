


class Entity(object):
    """Base type for all types."""
    
    def __init__(self, name, parent):
        super().__init__()
        
        self._name = name
        self._parent = parent
        
        
    @classmethod
    def from_path(cls, path):
        """Get the entity of a certain type from the given path. It the path is not 
        something that represents a given type, return None.
        
        Args:
            path: (str) The file path string.
            
        Returns:
            Entity subclass instance or None.
        
        """
        raise NotImplementedError