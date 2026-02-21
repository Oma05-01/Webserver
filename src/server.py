import socket
import threading
import time
import queue
import signal
import sys

shutdown_event = threading.Event()

MAX_THREADS = 50
thread_limiter = threading.Semaphore(MAX_THREADS)

WORKER_COUNT = 10
task_queue = queue.Queue()

HOST = "127.0.0.1"
PORT = 8080

server_socket = None

# --- Handlers ---
def validate_request(request):
    if not request:
        return False, "400", "Bad Request"

    method = request.get("method")
    path = request.get("path")
    version = request.get("version")

    # Only allow GET
    if method != "GET":
        return False, "405", "Method Not Allowed"

    # Validate HTTP version
    if version not in ("HTTP/1.0", "HTTP/1.1"):
        return False, "505", "HTTP Version Not Supported"

    # Basic path validation
    if not path or not path.startswith("/"):
        return False, "400", "Bad Request"

    # Host header required for HTTP/1.1
    if "Host" not in request["headers"]:
        return False, 400, "Bad Request"

    return True, None, None

def handle_client(client_socket):
    client_socket.settimeout(5)
    try:

        client_socket.settimeout(5)

        buffer = b""

        while b"\r\n\r\n" not in buffer:
            chunk = client_socket.recv(4096)
            if not chunk:
                break
            buffer += chunk

        if not buffer:
            return

        # Convert raw bytes to structured data
        request = parse_request(buffer)

        if not request:
            response_bytes = (
                "HTTP/1.1 400 Bad Request\r\n"
                "Content-Length: 0\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode("utf-8")
            client_socket.sendall(response_bytes)
            return

        is_valid, status_code, status_text = validate_request(request)

        if not is_valid:
            print(f"Rejected request: {status_code} {status_text}")

            response_bytes = (
                f"HTTP/1.1 {status_code} {status_text}\r\n"
                "Content-Length: 0\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode("utf-8")
            client_socket.sendall(response_bytes)
            print("-" * 30)
            return

        # A. ROUTING: Find the right function
        base_handler = resolve_route(request['path'])

        # We wrap the base handler with our middleware chain
        final_handler = apply_middlewares(base_handler, middlewares)

        # B. EXECUTION: Run the function to get the data
        response_data = final_handler(request)

        body_bytes = response_data['body'].encode('utf-8')

        # C. SERIALIZATION: Turn the dictionary into an HTTP string
        # (This is the ONLY place that knows about HTTP format)
        response_bytes = (
            f"HTTP/1.1 {response_data['status']} {response_data['status_text']}\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            "Content-Type: text/plain\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode('utf-8') + body_bytes

        # D. SENDING
        client_socket.sendall(response_bytes)
        print("-" * 30)

    except socket.timeout:
        print("Request timed out.")
        response = (
            "HTTP/1.1 408 Request Timeout\r\n"
            "Connection: close\r\n"
            "Content-Length: 0\r\n"
            "\r\n"
        )
        try:
            client_socket.sendall(response.encode())
        except:
            pass

    except Exception as e:
        print(f"Error handling client: {e}")

    finally:
        client_socket.close()

def limited_handle_client(client_socket):
    with thread_limiter:
        handle_client(client_socket)

def handle_home(request):
    time.sleep(5)
    return {
        "status": 200,
        "status_text": "OK",
        "body": "Welcome to the Home Page!"
    }

def handle_health(request):
    return {
        "status": 200,
        "status_text": "OK",
        "body": "System is healthy."
    }

def handle_404(request):
    return {
        "status": 404,
        "status_text": "Not Found",
        "body": "Oops! That path does not exist."
    }

def resolve_route(path):
    # .get() looks up the key; if not found, returns the second argument (default)
    handler = routes.get(path, handle_404)
    return handler

def worker():
    while not shutdown_event.is_set():
        try:
            client_socket = task_queue.get(timeout=1)
        except queue.Empty:
            continue
        try:
            handle_client(client_socket)
        except Exception as e:
            pass
        finally:
            task_queue.task_done()

routes = {
    "/": handle_home,
    "/health": handle_health,
}

# --- MIDDLEWARES ---

def logging_middleware(handler):
    def wrapped_handler(request):
        # 1. Pre-processing
        print(f"--> {request['method']} {request['path']}")

        # 2. Call the next layer
        response = handler(request)

        # 3. Post-processing
        print(f"<-- {response['status']} {response['status_text']}")
        return response

    return wrapped_handler

def timing_middleware(handler):
    def wrapped_handler(request):
        # 1. Start Timer
        start_time = time.time()

        # 2. Call the next layer
        response = handler(request)

        # 3. Stop Timer & Print
        duration = (time.time() - start_time) * 1000
        print(f"    (Took {duration:.2f}ms)")
        return response

    return wrapped_handler


# Define the order: Outer first, Inner last
middlewares = [logging_middleware, timing_middleware]

def apply_middlewares(handler, middleware_list):
    # We apply in reverse so the first item in the list becomes the OUTERMOST shell.
    # Goal: Log( Time( Handler ) )
    for middleware in reversed(middleware_list):
        handler = middleware(handler)
    return handler

def parse_request(raw_data):
    """
    Turns raw HTTP bytes into a structured dictionary.
    """
    if not raw_data:
        return None

    try:
        # Decode bytes to string
        request_text = raw_data.decode('utf-8')

        # Split into lines (CRLF)
        lines = request_text.split('\r\n')

        # Parse the Request Line (Top line: GET / HTTP/1.1)
        request_line = lines[0]
        words = request_line.split(' ')
        method = words[0]
        path = words[1]
        version = words[2]

        # Parse Headers (The rest of the lines)
        headers = {}
        for line in lines[1:]:
            if line == "": break  # Stop at the empty line
            if ': ' in line:
                key, value = line.split(': ', 1)
                headers[key] = value

        return {
            "method": method,
            "path": path,
            "version": version,
            "headers": headers
        }
    except Exception as e:
        print(f"Error parsing request: {e}")
        return None

def start_server():
    global server_socket

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server_socket.bind((HOST, PORT))
    server_socket.listen(5)

    print(f"Listening on {HOST}:{PORT}")

    # Start worker threads
    for _ in range(WORKER_COUNT):
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    while not shutdown_event.is_set():
        try:
            client_socket, client_address = server_socket.accept()
            task_queue.put(client_socket)
            print(f"Connection from {client_address}")

            # thread = threading.Thread(
            #     target=limited_handle_client,
            #     args=(client_socket,)
            # )
            # thread.start()
        except OSError:
            break

    print("Waiting for workers to finish...")
    task_queue.join()
    print("All tasks completed.")

def shutdown_server(signum, frame):
    print("\nShutting down server...")
    shutdown_event.set()

    if server_socket:
        server_socket.close()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown_server)
    start_server()
