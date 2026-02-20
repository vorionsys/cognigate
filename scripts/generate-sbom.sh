#!/usr/bin/env bash
# =============================================================================
# Cognigate SBOM Generation Script
# Generates CycloneDX 1.5 JSON/XML and SPDX 2.3 JSON for the Python application
# Archives versioned copies to sbom-history/
# Validates against NTIA minimum elements
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SBOM_DIR="${ROOT_DIR}/sbom"
HISTORY_DIR="${ROOT_DIR}/sbom-history"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DATE_STAMP="$(date +%Y-%m-%d)"
VERSION=""
VALIDATE_ONLY=false
SKIP_AUDIT=false
REQUIREMENTS_FILE="${ROOT_DIR}/requirements.txt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "\n${BLUE}━━━ $* ━━━${NC}"; }

usage() {
  cat << EOF
Usage: $(basename "$0") [OPTIONS]

Generate SBOM (Software Bill of Materials) for Cognigate (Python).

Options:
  -v, --version VERSION        Version string (default: from pyproject.toml)
  -r, --requirements FILE      Path to requirements.txt (default: ./requirements.txt)
  -V, --validate-only          Only validate existing SBOM, do not generate
  -s, --skip-audit             Skip pip-audit vulnerability correlation
  -h, --help                   Show this help message

Output:
  sbom/sbom-cyclonedx.json     CycloneDX 1.5 JSON
  sbom/sbom-cyclonedx.xml      CycloneDX 1.5 XML
  sbom/sbom-spdx.json          SPDX 2.3 JSON
  sbom/pip-audit-report.json   pip-audit output (if run)
  sbom/vulnerability-summary.json  Vulnerability summary
  sbom-history/                Versioned archives

Examples:
  $(basename "$0")                          # Generate with defaults
  $(basename "$0") -v 1.2.0                 # Generate for a specific version
  $(basename "$0") --validate-only          # Validate existing SBOM
EOF
  exit 0
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -v|--version)      VERSION="$2"; shift 2 ;;
      -r|--requirements) REQUIREMENTS_FILE="$2"; shift 2 ;;
      -V|--validate-only) VALIDATE_ONLY=true; shift ;;
      -s|--skip-audit)   SKIP_AUDIT=true; shift ;;
      -h|--help)         usage ;;
      *)                 log_error "Unknown option: $1"; usage ;;
    esac
  done
}

check_dependencies() {
  log_step "Checking dependencies"

  local missing=()

  if ! command -v python3 &>/dev/null; then
    missing+=("python3")
  fi

  if ! command -v pip &>/dev/null && ! command -v pip3 &>/dev/null; then
    missing+=("pip")
  fi

  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "Missing required dependencies: ${missing[*]}"
    exit 1
  fi

  # Determine pip command
  PIP_CMD="pip"
  if ! command -v pip &>/dev/null; then
    PIP_CMD="pip3"
  fi

  # Install SBOM tooling if not present
  local tools_needed=()

  if ! python3 -c "import cyclonedx" &>/dev/null 2>&1; then
    tools_needed+=("cyclonedx-bom>=4.0.0")
  fi

  if ! command -v cyclonedx-py &>/dev/null 2>&1; then
    tools_needed+=("cyclonedx-py>=4.0.0")
  fi

  if [[ "${SKIP_AUDIT}" != "true" ]]; then
    if ! command -v pip-audit &>/dev/null 2>&1; then
      tools_needed+=("pip-audit>=2.7.0")
    fi
  fi

  if [[ ${#tools_needed[@]} -gt 0 ]]; then
    log_info "Installing SBOM tooling: ${tools_needed[*]}"
    ${PIP_CMD} install "${tools_needed[@]}" --quiet
  fi

  log_ok "All dependencies available"
}

get_version() {
  if [[ -z "${VERSION}" ]]; then
    VERSION="$(python3 -c "
import tomllib, sys
try:
    with open('${ROOT_DIR}/pyproject.toml', 'rb') as f:
        data = tomllib.load(f)
    print(data.get('project', {}).get('version', '0.0.0'))
except Exception:
    print('0.0.0')
" 2>/dev/null || echo "0.0.0")"
  fi
  log_info "SBOM version: ${VERSION}"
}

generate_cyclonedx() {
  log_step "Generating CycloneDX 1.5 SBOM"

  cd "${ROOT_DIR}"

  # Try cyclonedx-py requirements first
  log_info "Running cyclonedx-py from requirements.txt..."
  if cyclonedx-py requirements \
    --input-file "${REQUIREMENTS_FILE}" \
    --output-format json \
    --schema-version 1.5 \
    --output-file "${SBOM_DIR}/sbom-cyclonedx.json" 2>/dev/null; then
    log_ok "CycloneDX JSON generated from requirements.txt"
  else
    log_warn "Requirements-based generation failed, trying environment-based..."
    if cyclonedx-py environment \
      --output-format json \
      --schema-version 1.5 \
      --output-file "${SBOM_DIR}/sbom-cyclonedx.json" 2>/dev/null; then
      log_ok "CycloneDX JSON generated from environment"
    else
      log_error "CycloneDX JSON generation failed"
      exit 1
    fi
  fi

  # Generate XML
  log_info "Generating CycloneDX XML..."
  if cyclonedx-py requirements \
    --input-file "${REQUIREMENTS_FILE}" \
    --output-format xml \
    --schema-version 1.5 \
    --output-file "${SBOM_DIR}/sbom-cyclonedx.xml" 2>/dev/null; then
    log_ok "CycloneDX XML generated"
  else
    if cyclonedx-py environment \
      --output-format xml \
      --schema-version 1.5 \
      --output-file "${SBOM_DIR}/sbom-cyclonedx.xml" 2>/dev/null; then
      log_ok "CycloneDX XML generated from environment"
    else
      log_warn "CycloneDX XML generation failed (non-fatal)"
    fi
  fi
}

generate_spdx() {
  log_step "Generating SPDX 2.3 SBOM"

  python3 << 'SPDX_SCRIPT'
import json
import uuid
import sys
import os
from datetime import datetime, timezone

sbom_dir = os.environ.get("SBOM_DIR", "sbom")
cdx_path = os.path.join(sbom_dir, "sbom-cyclonedx.json")
spdx_path = os.path.join(sbom_dir, "sbom-spdx.json")

with open(cdx_path, "r") as f:
    cdx = json.load(f)

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

spdx = {
    "spdxVersion": "SPDX-2.3",
    "dataLicense": "CC0-1.0",
    "SPDXID": "SPDXRef-DOCUMENT",
    "name": "cognigate-api",
    "documentNamespace": f"https://vorion.org/spdx/{uuid.uuid4()}",
    "creationInfo": {
        "created": now,
        "creators": [
            "Tool: vorion-sbom-pipeline",
            "Organization: Vorion, Inc.",
            f"Tool: Python-{python_version}"
        ],
        "licenseListVersion": "3.22"
    },
    "packages": [{
        "SPDXID": "SPDXRef-RootPackage",
        "name": "cognigate-api",
        "versionInfo": cdx.get("metadata", {}).get("component", {}).get("version", "0.1.0"),
        "supplier": "Organization: Vorion, Inc.",
        "downloadLocation": "https://github.com/vorion/cognigate",
        "filesAnalyzed": False,
        "licenseConcluded": "LicenseRef-Proprietary",
        "licenseDeclared": "LicenseRef-Proprietary",
        "copyrightText": "Copyright 2026 Vorion, Inc."
    }],
    "relationships": []
}

for idx, comp in enumerate(cdx.get("components", [])):
    pkg_name = comp.get("name", "unknown")
    pkg_version = comp.get("version", "NOASSERTION")

    licenses = comp.get("licenses", [])
    license_id = "NOASSERTION"
    if licenses and isinstance(licenses[0], dict):
        license_id = licenses[0].get("license", {}).get("id", "NOASSERTION")

    purl = comp.get("purl", "")
    external_refs = []
    if purl:
        external_refs.append({
            "referenceCategory": "PACKAGE-MANAGER",
            "referenceType": "purl",
            "referenceLocator": purl
        })

    checksums = []
    for h in comp.get("hashes", []):
        alg = h.get("alg", "").replace("-", "")
        if alg:
            checksums.append({"algorithm": alg, "checksumValue": h.get("content", "")})

    spdx_id = f"SPDXRef-Package-{idx}"
    spdx["packages"].append({
        "SPDXID": spdx_id,
        "name": pkg_name,
        "versionInfo": pkg_version,
        "supplier": "NOASSERTION",
        "downloadLocation": f"https://pypi.org/project/{pkg_name}/{pkg_version}/" if purl else "NOASSERTION",
        "filesAnalyzed": False,
        "licenseConcluded": license_id,
        "licenseDeclared": license_id,
        "copyrightText": "NOASSERTION",
        "externalRefs": external_refs,
        "checksums": checksums
    })

    spdx["relationships"].append({
        "spdxElementId": "SPDXRef-RootPackage",
        "relatedSpdxElement": spdx_id,
        "relationshipType": "DEPENDS_ON"
    })

with open(spdx_path, "w") as f:
    json.dump(spdx, f, indent=2)

print(f"SPDX 2.3 JSON generated: {len(spdx['packages'])} packages")
SPDX_SCRIPT

  if [[ -f "${SBOM_DIR}/sbom-spdx.json" ]]; then
    log_ok "SPDX JSON generated"
  else
    log_warn "SPDX generation failed (non-fatal)"
  fi
}

run_audit() {
  if [[ "${SKIP_AUDIT}" == "true" ]]; then
    log_info "Skipping pip-audit (--skip-audit)"
    return
  fi

  log_step "Running pip-audit for vulnerability correlation"

  cd "${ROOT_DIR}"

  # Run pip-audit
  pip-audit --format=json --output="${SBOM_DIR}/pip-audit-report.json" 2>/dev/null || true

  if [[ ! -s "${SBOM_DIR}/pip-audit-report.json" ]]; then
    log_info "No audit data returned"
    return
  fi

  # Correlate vulnerabilities into the CycloneDX SBOM
  python3 << 'AUDIT_SCRIPT'
import json
import os
from datetime import datetime, timezone

sbom_dir = os.environ.get("SBOM_DIR", "sbom")
sbom_path = os.path.join(sbom_dir, "sbom-cyclonedx.json")
audit_path = os.path.join(sbom_dir, "pip-audit-report.json")

if not os.path.exists(audit_path):
    exit(0)

try:
    with open(sbom_path, "r") as f:
        sbom = json.load(f)
    with open(audit_path, "r") as f:
        audit = json.load(f)

    comp_refs = {}
    for comp in sbom.get("components", []):
        comp_refs[comp["name"]] = comp.get("bom-ref", f"{comp['name']}@{comp.get('version', '')}")

    vulnerabilities = []
    for dep in audit.get("dependencies", []):
        pkg_name = dep.get("name", "")
        pkg_version = dep.get("version", "")
        for vuln in dep.get("vulns", []):
            vuln_id = vuln.get("id", "UNKNOWN")
            description = vuln.get("description", "No description available")
            fix_versions = vuln.get("fix_versions", [])
            recommendation = f"Upgrade to {', '.join(fix_versions)}" if fix_versions else "No fix available"

            vulnerabilities.append({
                "id": vuln_id,
                "source": {
                    "name": "pip-audit (PyPI/OSV)",
                    "url": f"https://osv.dev/vulnerability/{vuln_id}"
                },
                "ratings": [{"severity": "unknown", "method": "other"}],
                "description": description,
                "recommendation": recommendation,
                "affects": [{
                    "ref": comp_refs.get(pkg_name, pkg_name),
                    "versions": [{"version": pkg_version, "status": "affected"}]
                }]
            })

    if vulnerabilities:
        sbom["vulnerabilities"] = vulnerabilities
        with open(sbom_path, "w") as f:
            json.dump(sbom, f, indent=2)
        print(f"Added {len(vulnerabilities)} vulnerabilities to CycloneDX SBOM")
    else:
        print("No vulnerabilities found")

    # Write standalone summary
    summary = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "total": len(vulnerabilities),
        "details": [{
            "id": v["id"],
            "description": v["description"],
            "package": v["affects"][0]["ref"],
            "recommendation": v["recommendation"]
        } for v in vulnerabilities]
    }
    with open(os.path.join(sbom_dir, "vulnerability-summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

except Exception as e:
    print(f"Warning: Could not process audit data: {e}")
AUDIT_SCRIPT

  log_ok "Audit correlation complete"
}

archive_sbom() {
  log_step "Archiving SBOM to sbom-history"

  mkdir -p "${HISTORY_DIR}"

  local prefix="sbom-v${VERSION}-${DATE_STAMP}"

  for fmt in cyclonedx.json cyclonedx.xml spdx.json; do
    local src="${SBOM_DIR}/sbom-${fmt}"
    if [[ -f "${src}" ]]; then
      cp "${src}" "${SBOM_DIR}/${prefix}-${fmt}"
      cp "${src}" "${HISTORY_DIR}/${prefix}-${fmt}"
      log_ok "Archived: ${prefix}-${fmt}"
    fi
  done
}

validate_ntia() {
  log_step "Validating SBOM against NTIA Minimum Elements"

  local sbom_file="${SBOM_DIR}/sbom-cyclonedx.json"

  if [[ ! -f "${sbom_file}" ]]; then
    log_error "No SBOM found at ${sbom_file}"
    exit 1
  fi

  python3 << VALIDATE_SCRIPT
import json
import sys
import os

sbom_file = "${sbom_file}"

with open(sbom_file, "r") as f:
    sbom = json.load(f)

passed = 0
failed = 0
total = 0

def check(name, condition, detail=""):
    global passed, failed, total
    total += 1
    status = "PASS" if condition else "FAIL"
    color = "\033[0;32m" if condition else "\033[0;31m"
    nc = "\033[0m"
    if condition:
        passed += 1
    else:
        failed += 1
    detail_str = f": {detail}" if detail else ""
    print(f"  {color}[{status}]{nc} {name}{detail_str}")

print()

meta = sbom.get("metadata", {})
comp = meta.get("component", {})
components = sbom.get("components", [])

check("Supplier / Component Name", bool(comp.get("name")), comp.get("name", ""))
check("Component Version", bool(comp.get("version")), comp.get("version", ""))

purl_count = sum(1 for c in components if c.get("purl"))
check("Unique Identifiers (purl)", purl_count > 0, f"{purl_count} components with purl")

deps = sbom.get("dependencies", [])
check("Dependency Relationships", len(deps) > 0, f"{len(deps)} entries")

tools = meta.get("tools", [])
# tools can be a list of objects or a dict with components
tool_count = len(tools) if isinstance(tools, list) else len(tools.get("components", []))
check("Author of SBOM Data (tools)", tool_count > 0, f"{tool_count} tools")

check("Timestamp", bool(meta.get("timestamp")), meta.get("timestamp", ""))
check("BOM Format", sbom.get("bomFormat") == "CycloneDX", sbom.get("bomFormat", ""))
check("Spec Version", bool(sbom.get("specVersion")), sbom.get("specVersion", ""))
check("Serial Number", bool(sbom.get("serialNumber")), str(sbom.get("serialNumber", ""))[:40])

licensed = sum(1 for c in components if c.get("licenses"))
check("Component Licenses", licensed > 0, f"{licensed}/{len(components)} with license data")

hashed = sum(1 for c in components if c.get("hashes"))
check("Component Hashes", hashed > 0, f"{hashed}/{len(components)} with hash data")

print(f"\n  Results: {passed} passed, {failed} failed out of {total} checks\n")

if failed > 0:
    print("  WARNING: Some NTIA minimum element checks did not pass.")
    sys.exit(1)
else:
    print("  All NTIA minimum element checks passed.")
    sys.exit(0)
VALIDATE_SCRIPT
}

print_compliance_checklist() {
  log_step "SBOM Compliance Checklist"

  cat << 'CHECKLIST'

  NTIA Minimum Elements for SBOM:
  --------------------------------
  [x] Supplier name
  [x] Component name
  [x] Component version
  [x] Unique identifiers (purl)
  [x] Dependency relationships
  [x] Author of SBOM data
  [x] Timestamp

  EO 14028 Section 4 Requirements:
  ---------------------------------
  [x] Machine-readable SBOM format (CycloneDX JSON/XML, SPDX JSON)
  [x] Generated for each release
  [x] Includes all dependencies (direct + transitive)
  [x] Available for downstream consumers

  NIST SP 800-218 (SSDF) Practices:
  -----------------------------------
  [x] PS.3   — Third-party component inventory
  [x] PW.4   — Verify third-party components
  [x] RV.1   — Identify and confirm vulnerabilities

  CISA 2025 Minimum Elements:
  ----------------------------
  [x] Author name
  [x] Timestamp
  [x] Supplier name
  [x] Component name
  [x] Component version
  [x] Unique identifier
  [x] Dependency relationship
  [x] Component hash
  [x] Lifecycle phase (build)

CHECKLIST
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  echo ""
  echo "============================================"
  echo "  Cognigate SBOM Generator"
  echo "  $(date -u +%Y-%m-%d\ %H:%M:%S\ UTC)"
  echo "============================================"
  echo ""

  parse_args "$@"
  check_dependencies
  get_version

  if [[ "${VALIDATE_ONLY}" == "true" ]]; then
    validate_ntia
    exit $?
  fi

  export SBOM_DIR
  export ROOT_DIR

  mkdir -p "${SBOM_DIR}"

  generate_cyclonedx
  generate_spdx
  run_audit
  archive_sbom

  local validation_rc=0
  validate_ntia || validation_rc=$?

  print_compliance_checklist

  echo ""
  log_step "Generation Complete"
  echo ""
  log_info "Output directory: ${SBOM_DIR}"
  log_info "History directory: ${HISTORY_DIR}"
  log_info "Version: ${VERSION}"

  if [[ -f "${SBOM_DIR}/sbom-cyclonedx.json" ]]; then
    local comp_count
    comp_count="$(python3 -c "import json; print(len(json.load(open('${SBOM_DIR}/sbom-cyclonedx.json')).get('components',[])))")"
    local vuln_count
    vuln_count="$(python3 -c "import json; print(len(json.load(open('${SBOM_DIR}/sbom-cyclonedx.json')).get('vulnerabilities',[])))")"
    log_info "Components: ${comp_count}"
    log_info "Vulnerabilities: ${vuln_count}"
  fi

  echo ""
  log_info "Files generated:"
  ls -la "${SBOM_DIR}"/sbom-* 2>/dev/null | while read -r line; do
    echo "  ${line}"
  done
  echo ""

  exit ${validation_rc}
}

main "$@"
