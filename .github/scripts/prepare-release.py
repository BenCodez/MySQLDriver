"""Validate the shaded plugin and stage versioned, byte-for-byte release assets."""
import argparse
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


def project_version(project):
    version = ET.parse(project / "pom.xml").getroot().findtext(
        "{http://maven.apache.org/POM/4.0.0}version"
    )
    if not version or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,2}", version):
        raise ValueError("Use a stable numeric Maven version, such as 1.0 or 1.0.1")
    return version


def select_tag(project, event, ref, requested_version=""):
    if event == "workflow_dispatch":
        if ref != "refs/heads/master":
            raise ValueError("Releases must be dispatched from the master branch")
        if requested_version != project_version(project):
            raise ValueError("Release version must match the Maven version, without the v prefix")
        return f"v{requested_version}"
    if event == "push" and ref.startswith("refs/tags/"):
        tag = ref.removeprefix("refs/tags/")
        if tag != f"v{project_version(project)}":
            raise ValueError("Release tag must match the Maven version")
        return tag
    return ""


def prepare(project, tag=""):
    version = project_version(project)
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--select-tag", action="store_true", help="Validate the workflow request before building")
    args = parser.parse_args()
    if args.select_tag:
        tag = select_tag(Path("MySQLDriver"), os.environ["RELEASE_EVENT"],
                         os.environ["RELEASE_REF"], os.environ.get("RELEASE_VERSION", ""))
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(f"tag={tag}\n")
    else:
        print(prepare(Path("MySQLDriver"), os.environ.get("RELEASE_TAG", "")))
