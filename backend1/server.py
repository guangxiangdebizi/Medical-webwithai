#!/usr/bin/env python3
"""
Dolphin Trinity AI™ Backend Server Launcher
Starts the FastAPI server on port 8081
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8081,
        reload=False,
        workers=1,
        log_level="info"
    )


