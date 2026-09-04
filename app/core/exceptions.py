class PipelineError(Exception):
    """Raised when a pipeline stage fails in a way that should abort the run."""
