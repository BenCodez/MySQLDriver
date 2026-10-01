"""Validate the shaded plugin and stage versioned, byte-for-byte release assets."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile


DRIVERS = ("com.mysql.cj.jdbc.Driver", "org.mariadb.jdbc.Driver", "org.postgresql.Driver")
PLUGIN_CLASSES = (
    "com/bencodez/mysqldriver/spigot/DriverPluginSpigot.class",
    "com/bencodez/mysqldriver/bungee/DriverPluginBungee.class",
    "com/bencodez/mysqldriver/velocity/MySQLDriverVelocity.class",
)


def prepare(project, tag=""):
    version = ET.parse(project / "pom.xml").getroot().findtext(
        "{http://maven.apache.org/POM/4.0.0}version"
    )
    if not version or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,2}", version):
        raise ValueError("Use a stable numeric Maven version, such as 1.0 or 1.0.1")
    if tag and tag != f"v{version}":
        raise ValueError(f"Release tag {tag!r} must match Maven version v{version}")

    # maven-jar-plugin's finalName is MySQLDriver; Shade replaces that artifact.
    source = project / "target/MySQLDriver.jar"
    with zipfile.ZipFile(source) as jar:
        if jar.testzip() is not None:
            raise ValueError("Corrupt plugin JAR")
        for entry in (*PLUGIN_CLASSES, *(driver.replace(".", "/") + ".class" for driver in DRIVERS)):
            if entry not in jar.namelist():
                raise ValueError(f"Shaded plugin is missing {entry}")
        providers = {
            line.split("#", 1)[0].strip()
            for line in jar.read("META-INF/services/java.sql.Driver").decode().splitlines()
        }
        if not set(DRIVERS).issubset(providers):
            raise ValueError("Shaded plugin is missing JDBC service providers")
        for descriptor in ("plugin.yml", "bungee.yml"):
            text = jar.read(descriptor).decode()
            if not re.search(r"(?m)^version:\s*['\"]?" + re.escape(version) + r"['\"]?\s*$", text):
                raise ValueError(f"{descriptor} version must match Maven version {version}")
        if json.loads(jar.read("velocity-plugin.json"))["version"] != version:
            raise ValueError(f"Velocity plugin version must match Maven version {version}")

    destination = project / "target/release"
    destination.mkdir()  # Refuse stale output; Maven clean creates a fresh target.
    artifact = destination / f"MySQLDriver-{version}.jar"
    shutil.copyfile(source, artifact)
    checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
    artifact.with_suffix(".jar.sha256").write_text(f"{checksum}  {artifact.name}\n", encoding="ascii")
    return artifact


if __name__ == "__main__":
    print(prepare(Path("MySQLDriver"), os.environ.get("RELEASE_TAG", "")))
