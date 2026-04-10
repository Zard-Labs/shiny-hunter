"""
PyInstaller entry point for the ShinyStarter backend.

This script is the entry point when running as a bundled executable.
It starts the uvicorn server with the FastAPI app.
"""

import os
import sys
import uvicorn


def get_port():
    """Get the port from environment or default to 8000."""
    return int(os.environ.get('SHINYSTARTER_PORT', '8000'))


def main():
    port = get_port()
    print(f"Starting ShinyStarter backend on port {port}...")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        # No reload in production
        reload=False,
        # Single worker for desktop app
        workers=1,
    )


if __name__ == "__main__":
    main()
