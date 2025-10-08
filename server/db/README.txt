- This applies to Windows users
- You will need PostgreSQL installed at C:\Program Files\PostgreSQL\18
- pg_hba.conf will need to be setup properly. Scroll to the end of the file and you should see:

# TYPE  DATABASE	USER		ADDRESS			METHOD

- Fill in the above with your desired configuration.

- To verify that PostgreSQL is running:
Press Win+R, type services.msc, Enter.
Find the service named something like:
postgresql-x64-16 (version may differ: -15, -14, etc.)
Check:
Status: Running
Startup Type: Automatic (or Automatic (Delayed Start))
If it’s not running, right‑click → Start.
To auto-start on boot, right‑click → Properties → set Startup type to Automatic → Apply.

- Create the database PowerShell or Command Prompt: "C:\Program Files\PostgreSQL\18\bin\psql.exe" "postgresql://postgres:<yourpassword>@localhost:5432/postgres" -c "CREATE DATABASE parkageddon;"

- Load your init SQL into the new DB. This command is just an example and you will need to supply your own path to the Parkageddon_init.sql file: "C:\Program Files\PostgreSQL\18\bin\psql.exe" "postgresql://postgres:<yourpassword>@localhost:5432/parkageddon" -f "C:\Users\jorda\Documents\Github\Parkageddon\server\db\Parkageddon_init.sql"

