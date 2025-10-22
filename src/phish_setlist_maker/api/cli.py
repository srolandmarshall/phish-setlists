"""CLI entry points for the Phish Setlist Maker API."""

import sys


def start_server():
    """Start the FastAPI development server with uvicorn."""
    import uvicorn
    
    # Parse simple command-line args
    host = "127.0.0.1"
    port = 8000
    
    for arg in sys.argv[1:]:
        if arg.startswith("--host="):
            host = arg.split("=", 1)[1]
        elif arg.startswith("--port="):
            port = int(arg.split("=", 1)[1])
        elif arg in ("-h", "--help"):
            print("Usage: poetry run server [--host=HOST] [--port=PORT]")
            print("\nStart the Phish Setlist Maker API server")
            print("\nOptions:")
            print("  --host=HOST   Host to bind to (default: 127.0.0.1)")
            print("  --port=PORT   Port to bind to (default: 8000)")
            print("  -h, --help    Show this help message")
            print("\nExamples:")
            print("  poetry run server")
            print("  poetry run http-start")
            print("  poetry run server --port=8080")
            print("  poetry run server --host=0.0.0.0 --port=3000")
            return
    
    print(f"🎵 Starting Phish Setlist Maker API server...")
    print(f"📡 Server: http://{host}:{port}")
    print(f"📚 API Docs: http://{host}:{port}/docs")
    print(f"🎸 Generate: http://{host}:{port}/generate")
    print()
    
    uvicorn.run(
        "phish_setlist_maker.api:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    start_server()
