KUVIS - Karachi Urban Vulnerability Intelligence System
Portable Windows release
=======================================================

WHAT THIS IS
  The complete KUVIS web application with all of its results: the 500 m analysis grid of Karachi, the
  five data-mining modules (heat, flood, urban change, infrastructure, vulnerability index), the
  location reports with PDF export, the discoveries and the methodology pages. Everything runs on
  this computer; nothing is installed and nothing outside this folder is changed.

REQUIREMENTS
  - Windows 10 or 11, 64-bit
  - About 3 GB of free disk space after extraction
  - A modern browser (Edge, Chrome or Firefox)
  - Internet only for the background map (satellite / grey basemap and place labels).
    Without internet the KUVIS data layers, charts and reports still work, on a blank background.

HOW TO RUN
  1. Extract the whole zip file to a normal folder, for example Desktop or Documents.
     (Do not run it from inside the zip, and avoid C:\Program Files.)
  2. Double-click START_KUVIS.bat.
       - The FIRST start builds the local database from data\kuvis.dump. This takes a few minutes,
         once. Later starts take a few seconds.
       - Your browser opens KUVIS automatically (normally at http://localhost:8000).
  3. Keep the black KUVIS window open while you use the app.
  4. To stop: press Ctrl+C in the KUVIS window, or close it. If anything is left running,
     double-click STOP_KUVIS.bat.

IF SOMETHING GOES WRONG
  - "Windows protected your PC" (SmartScreen): click "More info" -> "Run anyway". The files are
    unsigned student software, not malware.
  - The browser did not open: look in the KUVIS window for the address (http://localhost:PORT)
    and open it yourself. If port 8000 is busy, KUVIS uses the next free port.
  - The first start stopped with an error: delete the folder data\pgdata and the file
    data\restore.ok, then start again. Log files are in data\logs.
  - Antivirus software may ask about postgres.exe or python.exe; they only listen on this
    computer (localhost), never on the network.

WHAT IS INSIDE
  START_KUVIS.bat       starts everything
  STOP_KUVIS.bat        stops the database if a window was closed abnormally
  kuvis_launcher.py     the start-up logic (database first-run setup, ports, server, browser)
  backend\              the FastAPI server (REST API + vector map tiles + web app)
  frontend\dist\        the compiled React + MapLibre web application
  data\kuvis.dump       the KUVIS PostGIS database (all grid cells, features, mining results)
  runtime\python\       Python 3.12 with the server's libraries
  runtime\pgsql\        PostgreSQL 17 + PostGIS
  docs\                 final report, results, methodology and data documentation

IMPORTANT CAVEATS (also shown in the app)
  - Land surface temperature (LST) is not air temperature.
  - Road density is not traffic congestion.
  - Missing data is shown as missing, never as zero.
  - The vulnerability index is a relative research index, NOT an official risk assessment.

Source code, pipeline and documentation: https://github.com/Hamza4fzal/KUVIS
Data credits: see docs\DATA_SOURCES.md (ESA, USGS/NASA, Copernicus, JRC, CHC/UCSB, WorldPop,
OpenStreetMap contributors, Microsoft Planetary Computer).
