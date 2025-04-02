from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
import os
import socket
import base64
import threading
import time

app = FastAPI()


def get_ntrip_config(caster=None, port=None, user=None, password=None):
    caster = caster or os.getenv("NTRIP_CASTER", "positionz-rt.linz.govt.nz")
    port = int(port or os.getenv("NTRIP_PORT", "2101"))
    user = user or os.getenv("NTRIP_USER", "test")
    password = password or os.getenv("NTRIP_PASS", "test")
    auth = base64.b64encode(f"{user}:{password}".encode()).decode()
    return caster, port, auth, user


@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <html>
    <head>
        <title>BNC GNSS Web API</title>
        <style>
            body { font-family: sans-serif; padding: 2rem; }
            h1 { margin-bottom: 1rem; }
            ul { list-style-type: none; padding-left: 0; }
            li { margin-bottom: 0.5rem; }
            a { text-decoration: none; color: #007acc; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>📡 BNC GNSS Web API</h1>
        <ul>
            <li><a href="/api/status">🩺 API Status</a></li>
            <li><a href="/api/mountpoints">📋 Mountpoints List</a></li>
            <li><a href="/api/mountpoint">🔍 Mountpoint</a></li>
        </ul>
    </body>
    </html>
    """


@app.get("/favicon.ico")
def favicon():
    # Return 204 No Content to avoid 404 noise
    return Response(status_code=204)


@app.get("/api/status")
def status():
    return {"message": "Backend running!"}



@app.get("/api/mountpoints", response_class=HTMLResponse)
def mountpoints_form():
    return """
    <html>
    <head>
        <title>BNC GNSS Web API - NTRIP Mountpoints Form</title>
        <style>
            body { font-family: sans-serif; padding: 2rem; }
            form label { display: block; margin: 0.5rem 0; }
            input { padding: 0.25rem; width: 300px; }
        </style>
    </head>
    <body>
        <h2>🔐 NTRIP Mountpoints Credentials</h2>
        <form method="post" action="/api/mountpoints" autocomplete="off">
            <label>Caster: <input name="caster" value="positionz-rt.linz.govt.nz" /></label>
            <label>Port: <input name="port" type="number" value="2101" /></label>
            <label>User: <input name="user" /></label>
            <label>Pass: <input name="password" type="password" /></label>
            <button type="submit">Submit</button>
        </form>
    </body>
    </html>
    """


@app.post("/api/mountpoints", response_class=HTMLResponse)
def list_mountpoints_post(
    caster: str = Form(...),
    port: int = Form(...),
    user: str = Form(...),
    password: str = Form(...)
):
    caster_host, caster_port, auth, user = get_ntrip_config(caster, port, user, password)
    response_data = fetch_source_table(caster_host, caster_port, auth)
    mountpoints = parse_mountpoints(response_data)

    results = []
    threads = []

    for mp in mountpoints:
        t = threading.Thread(target=test_mountpoint, args=(mp, results, caster_host, caster_port, auth))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    rows = ""
    for mp in sorted(results, key=lambda x: x["Mountpoint"]):
        rows += f"""
        <tr>
            <td>{mp['Mountpoint']}</td>
            <td>{mp['Format']}</td>
            <td>{mp['NavSys']}</td>
            <td>{mp['Carrier']}</td>
            <td>{mp['Lat']}</td>
            <td>{mp['Lon']}</td>
            <td>{mp['Auth']}</td>
            <td>{mp['NMEA']}</td>
            <td>{mp['Bitrate']}</td>
            <td style='color:{{"green" if mp["status"]=="✅ OK" else "red"}}'>{mp['status']}</td>
            <td>{mp['bytes']}</td>
        </tr>
        """

    return f"""
    <html>
    <head>
        <title>BNC GNSS Web API - NTRIP Mountpoints List</title>
        <style>
            body {{ font-family: sans-serif; padding: 1rem; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: left; }}
            th {{ background: #f0f0f0; }}
        </style>
    </head>
    <body>
        <h1>Mountpoints from {caster_host}:{caster_port} (user: {user})</h1>
        <table>
            <thead>
                <tr>
                    <th>Mountpoint</th>
                    <th>Format</th>
                    <th>NavSys</th>
                    <th>Carrier</th>
                    <th>Lat</th>
                    <th>Lon</th>
                    <th>Auth</th>
                    <th>NMEA</th>
                    <th>Bitrate</th>
                    <th>Status</th>
                    <th>Bytes</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        <p><a href="/api/mountpoints">⬅ Back</a></p>
    </body>
    </html>
    """


@app.api_route("/api/mountpoint", methods=["GET", "POST"], response_class=HTMLResponse)
async def mountpoint_form(request: Request):
    if request.method == "POST":
        form = await request.form()
        mountpoint = form.get("mountpoint")
        caster = form.get("caster")
        port = form.get("port")
        user = form.get("user")
        password = form.get("password")
        caster_host, caster_port, auth, _ = get_ntrip_config(caster, port, user, password)
        response_data = fetch_source_table(caster_host, caster_port, auth)
        mountpoints = parse_mountpoints(response_data)

        target = next((mp for mp in mountpoints if mp["Mountpoint"] == mountpoint), None)
        if not target:
            return HTMLResponse(f"<p>❌ Mountpoint '{mountpoint}' not found.</p>")

        result = []
        test_mountpoint(target, result, caster_host, caster_port, auth)
        r = result[0] if result else {"status": "❌ Fail", "bytes": 0}

        return HTMLResponse(f"""
        <html>
        <head><title>BNC GNSS Web API - NTRIP Mountpoint Form</title></head>
        <body>
            <h2>✅ Result for Mountpoint: {mountpoint}</h2>
            <ul>
                <li>Status: {r['status']}</li>
                <li>Bytes: {r['bytes']}</li>
                <li>Format: {target['Format']}</li>
                <li>NavSys: {target['NavSys']}</li>
                <li>Carrier: {target['Carrier']}</li>
                <li>Location: {target['Lat']}, {target['Lon']}</li>
            </ul>
            <p><a href="/api/mountpoint">⬅ Back</a></p>
        </body>
        </html>
        """)

    return HTMLResponse("""
    <html>
    <head><title>BNC GNSS Web API - NTRIP Mountpoint Search</title></head>
    <body>
        <h2>🔍 NTRIP Mountpoint Credentials</h2>
        <form method="post" action="/api/mountpoint">
            <label>Mountpoint: <input name="mountpoint" /></label><br>
            <label>Caster: <input name="caster" value="positionz-rt.linz.govt.nz" /></label><br>
            <label>Port: <input name="port" value="2101" /></label><br>
            <label>User: <input name="user" /></label><br>
            <label>Password: <input name="password" type="password" /></label><br>
            <button type="submit">Submit</button>
        </form>
        <p><a href="/">⬅ Back</a></p>
    </body>
    </html>
    """)


def fetch_source_table(host, port, auth):
    request = (
        "GET / HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "User-Agent: NTRIP PythonClient/1.0\r\n"
        f"Authorization: Basic {auth}\r\n"
        "Connection: close\r\n\r\n"
    )
    with socket.create_connection((host, port), timeout=10) as s:
        s.send(request.encode())
        response = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            response += chunk
    return response.decode(errors="ignore")


def parse_mountpoints(data):
    mountpoints = []
    for line in data.splitlines():
        if line.startswith("STR;"):
            parts = line.strip().split(";")
            if len(parts) >= 18:
                mountpoints.append({
                    "Mountpoint": parts[1],
                    "Format": parts[3],
                    "FormatDetails": parts[4],
                    "Carrier": parts[5],
                    "NavSys": parts[6],
                    "Network": parts[7],
                    "Country": parts[8],
                    "Lat": parts[9],
                    "Lon": parts[10],
                    "NMEA": parts[11],
                    "Solution": parts[12],
                    "Generator": parts[13],
                    "Compression": parts[14],
                    "Auth": parts[15],
                    "Fee": parts[16],
                    "Bitrate": parts[17],
                })
    return mountpoints


def test_mountpoint(mp, results, host, port, auth):
    name = mp["Mountpoint"]
    request = (
        f"GET /{name} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Ntrip-Version: Ntrip/2.0\r\n"
        f"User-Agent: NTRIP PythonClient/1.0\r\n"
        f"Authorization: Basic {auth}\r\n"
        f"Connection: close\r\n\r\n"
    )
    try:
        with socket.create_connection((host, port), timeout=10) as s:
            s.send(request.encode())
            header = s.recv(1024)
            if b"200 OK" not in header:
                results.append({**mp, "status": "❌ Fail", "bytes": 0})
                return

            total_bytes = 0
            start = time.time()
            s.settimeout(2)
            while time.time() - start < 3:
                try:
                    data = s.recv(4096)
                    if not data:
                        break
                    total_bytes += len(data)
                except socket.timeout:
                    break

            results.append({**mp, "status": "✅ OK", "bytes": total_bytes})
    except Exception:
        results.append({**mp, "status": "❌ Fail", "bytes": 0})


@app.post("/api/mountpoint/{mountpoint}", response_class=HTMLResponse)
def mountpoint_test(
    mountpoint: str,
    caster: str = Form(...),
    port: int = Form(...),
    user: str = Form(...),
    password: str = Form(...)
):
    caster_host, caster_port, auth, _ = get_ntrip_config(caster, port, user, password)
    response_data = fetch_source_table(caster_host, caster_port, auth)
    mountpoints = parse_mountpoints(response_data)

    target = next((mp for mp in mountpoints if mp["Mountpoint"] == mountpoint), None)
    if not target:
        return f"<p>❌ Mountpoint '{mountpoint}' not found.</p>"

    result = []
    test_mountpoint(target, result, caster_host, caster_port, auth)
    r = result[0] if result else {"status": "❌ Fail", "bytes": 0}

    return f"""
    <html>
    <head><title>Mountpoint Result</title></head>
    <body>
        <h2>✅ Result for Mountpoint: {mountpoint}</h2>
        <ul>
            <li>Status: {r['status']}</li>
            <li>Bytes: {r['bytes']}</li>
            <li>Format: {target['Format']}</li>
            <li>NavSys: {target['NavSys']}</li>
            <li>Carrier: {target['Carrier']}</li>
            <li>Location: {target['Lat']}, {target['Lon']}</li>
        </ul>
        <p><a href="/api/mountpoints">⬅ Back</a></p>
    </body>
    </html>
    """
