# Webserver
Minimal HTTP/1.1 server built from raw sockets to explore request lifecycle, concurrency, and middleware mechanics.

## Why This Project Exists;
Most backend developers only interact with web frameworks (Django, Flask, DRF), which abstract away the underlying request handling. This makes it easy to build apps but hides how requests flow, how concurrency is handled, and how middleware operates under load.

This project was designed to:
- Explore the full HTTP request lifecycle, from TCP socket to response
- Understand routing, middleware chains, and timeouts without framework magic
- Experience concurrency and resource management first-hand
- Close the gap between knowing how to “use a web framework” and understanding what happens under the hood in a real backend system

## Scope & Constraints
Included;
- Raw TCP socket handling to accept client connections
- Parsing HTTP/1.1 request lines, headers, and body
- Routing requests to handler functions based on method + path
- Middleware chain execution for pre/post-processing
- Thread-per-connection concurrency model
- Request timeouts to prevent resource starvation
- Graceful shutdown on termination signals

Explicitly Excluded;
- TLS / HTTPS support (handled by reverse proxies in production)
- HTTP/2 or later protocols (focus is on learning HTTP/1.1 mechanics)
- Static file optimizations or caching
- WSGI/ASGI compliance (framework integration is intentionally skipped)
- Production-level performance tuning or scalability features

## Architecture Overview
The web server is structured around three core components:
- TCP Server – Accepts client connections and reads raw bytes from sockets.
- HTTP Parser & Router – Parses incoming requests (method, path, headers, body) and routes them to the appropriate handler function.
- Middleware Chain & Response Writer – Processes requests through middleware, applies business logic, and writes properly formatted HTTP responses back to the client.

Request Flow: 
Client Request -> TCP Socket -> HTTP Parser -> Routing (method + path) -> Middleware Chain -> Request Handler -> Response Writer -> Client Response

**Concurrency Model**:

- Thread-per-connection: each incoming connection is handled in its own thread.
- Shared routing table and middleware chain are read-only to avoid locking overhead.
- Request timeouts prevent individual threads from being blocked indefinitely.

Key Notes:

- This design focuses on clarity and learning, not performance.
- All components are implemented from scratch using Python standard library only (no frameworks).
- Graceful shutdown is implemented to safely terminate active threads and close sockets.

## Key Design Decisions
1. Manual HTTP Parsing
- Chose to parse HTTP/1.1 requests from raw bytes instead of using http.server to fully understand how headers, request lines, and bodies are structured.
- Helps reveal edge cases like malformed requests and partial payloads.

2. Thread-per-Connection Concurrency
- Chosen for clarity over performance. Each incoming connection gets a dedicated thread, making it easy to reason about request flow and isolation.
- Demonstrates the tradeoff between simplicity and scalability.

3. Middleware as Explicit Chain
- Middleware functions are executed sequentially before/after the request handler.
- Provides insight into how frameworks like Django or Express handle authentication, logging, and other pre/post-processing tasks.

4. Hard Request Timeouts
- Enforces a maximum processing time per request to prevent thread exhaustion.
- Illustrates why production servers implement backpressure and request limits.

5. Graceful Shutdown Handling
- Implements SIGINT/SIGTERM handling to stop accepting new connections and allow active threads to finish.
- Demonstrates safe resource cleanup, which is critical in real-world systems.

## Failure Modes & Limitations
- Slow Clients Exhaust Threads – Because each connection uses a thread, a large number of slow clients can consume all available threads.
- Malformed Requests – Unexpected or malformed HTTP requests may cause early connection termination.
- Memory Usage Growth – Each thread and request object uses memory; memory usage grows linearly with concurrent connections.
- Limited Scalability – Thread-per-connection model is not suitable for thousands of concurrent connections.
- No TLS / HTTP/2 – Security and modern protocol features are intentionally excluded for learning focus.
- No Static File Optimizations or Caching – This server focuses on request lifecycle, not performance tuning.

## What I Learned
**Non-Obvious Insights**
- TCP is not HTTP. A socket server does not “speak HTTP” automatically. If you don’t send a valid HTTP response line and headers, clients will reject the connection.
- TCP is a stream, not packets. Even though the network MTU is ~1500 bytes, recv(4096) does not guarantee a full request. Data can arrive partially, which forced proper buffering.
- Content-Length must be byte-accurate. Calculating string length is incorrect when encoding is involved — HTTP operates on bytes, not Python strings.
- Concurrency is resource management, not just parallelism. Thread-per-connection works but can exhaust memory quickly. A thread pool provides controlled scalability.
- Sockets block by default. Without timeouts, a slow or malicious client can starve your server indefinitely.
- Graceful shutdown is deliberate engineering. Proper shutdown requires coordination between accept loops, worker threads, and task queues.
- HTTP correctness matters. Even something as small as a missing Host header can invalidate the entire request (as demonstrated using curl -H "Host:").

**Assumptions I Had That Turned Out Wrong**
- I assumed recv() returns the full request in one call.
- I assumed closing the socket after reading was sufficient.
- I assumed PowerShell curl was actual curl.
- I assumed concurrency meant “spawn more threads.”
- I underestimated how much work real web servers do before your application code runs.

**How Real Systems Differ from This Implementation**
- My server reads only headers and assumes no request body.
- It does not support keep-alive connections.
- It does not implement chunked transfer encoding.
- It does not support HTTP/2 or TLS.
- Error handling is simplified.
- Logging is unstructured and synchronous.
- There is no connection reuse or advanced I/O multiplexing.

## How Production Systems Do This Differently
**Compared to nginx**

**nginx:**
- Uses an event-driven architecture (epoll/kqueue), not thread-per-connection.
- Can handle tens of thousands of concurrent connections.
- Supports TLS termination, HTTP/2, HTTP/3.
- Implements advanced buffering, request parsing, and backpressure.
- Has worker process isolation for fault tolerance.

**Complexity introduced:**
- Event loops
- Non-blocking I/O
- State machines for partial parsing
- Advanced memory management
- Compared to Apache HTTP Server

**Apache:**
- Historically used process-per-connection or hybrid models.
- Supports dynamic module loading.
- Implements extensive configuration layers.

**Complexity introduced:**
- Process management
- Module lifecycle management
- Shared memory coordination
- Compared to Redis

**Redis:**
- Uses a single-threaded event loop for command execution.
- Uses I/O multiplexing.
- Has highly optimized memory layout.
- Implements persistence (RDB, AOF).
- Uses efficient data structures in C.

**Complexity introduced:**
- Custom memory allocator usage
- Event-driven networking
- Persistence guarantees
- Replication and clustering

**Compared to Apache Kafka
Kafka:**
- Uses append-only logs.
- Relies on zero-copy file transfer.
- Implements partitioning for scalability.
- Guarantees ordering within partitions.
- Handles replication and fault tolerance.

**Complexity introduced:**
- Distributed consensus
- Leader election
- Disk-backed durability
- Consumer offset tracking

## How to Run
Minimal steps:
```bash
python src/server.py
