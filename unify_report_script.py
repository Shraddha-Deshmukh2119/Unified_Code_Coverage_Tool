import xml.etree.ElementTree as ET
import json
import urllib.request
import urllib.error
import base64
import os
import sys
from datetime import datetime, timezone

# --- DYNAMIC CONFIGURATION ---
SONAR_PROJECT_KEY = os.getenv('SONAR_PROJECT_KEY')
SONAR_TOKEN = os.getenv('SONAR_TOKEN')

# These paths are passed from Jenkins based on the checkout directories
JAVA_XML_PATH = os.getenv('JAVA_XML_PATH')
CPP_XML_PATH = os.getenv('CPP_XML_PATH')

def get_java_details(xml_path):
    if not xml_path or not os.path.exists(xml_path):
        return {"language_coverage": "0.0%", "status": "File not found"}
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        data = {"classes": [], "totals": {}, "language_coverage": "0.0%"}
        
        for package in root.findall('package'):
            for sourcefile in package.findall('sourcefile'):
                counters = sourcefile.findall('counter')
                line_c = next((c for c in counters if c.get('type') == 'LINE'), None)
                data["classes"].append({
                    "name": f"{package.get('name')}/{sourcefile.get('name')}",
                    "lines_missed": line_c.get('missed') if line_c is not None else "0"
                })
        
        for counter in root.findall('counter'):
            c_type = counter.get('type')
            missed, covered = int(counter.get('missed')), int(counter.get('covered'))
            data["totals"][c_type] = {"missed": missed, "covered": covered}
            if c_type == 'LINE' and (missed + covered) > 0:
                data["language_coverage"] = f"{(covered / (missed + covered)) * 100:.2f}%"
        return data
    except Exception as e:
        return {"language_coverage": "0.0%", "error": str(e)}

def get_cpp_details(xml_path):
    if not xml_path or not os.path.exists(xml_path):
        return {"language_coverage": "0.0%", "status": "File not found"}
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        data = {"files": [], "totals": {}, "language_coverage": "0.0%"}
        t_l_miss, t_l_cov, t_b_miss, t_b_cov = 0, 0, 0, 0

        for file_node in root.findall('file'):
            f_path = file_node.get('path')
            f_name = f_path.replace('\\', '/').split('/')[-1]
            f_miss = 0
            for line in file_node.findall('lineToCover'):
                if line.get('covered') == 'true': t_l_cov += 1
                else: 
                    t_l_miss += 1
                    f_miss += 1
                
                branches = line.get('branchesToCover')
                if branches:
                    t_b_cov += int(line.get('coveredBranches', 0))
                    t_b_miss += (int(branches) - int(line.get('coveredBranches', 0)))

            data["files"].append({"name": f_name, "lines_missed": str(f_miss)})

        if (t_l_miss + t_l_cov) > 0:
            data["language_coverage"] = f"{(t_l_cov / (t_l_miss + t_l_cov)) * 100:.2f}%"
        data["totals"] = {
            "LINE": {"missed": t_l_miss, "covered": t_l_cov},
            "BRANCH": {"missed": t_b_miss, "covered": t_b_cov}
        }
        return data
    except Exception as e:
        return {"language_coverage": "0.0%", "error": str(e)}

def fetch_from_sonar(url):
    if not SONAR_TOKEN: return {}
    auth_str = f"{SONAR_TOKEN}:"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    headers = {"Authorization": f"Basic {encoded_auth}"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception: return {}

def main():
    if not SONAR_PROJECT_KEY:
        print("[ERROR] SONAR_PROJECT_KEY not set."); sys.exit(1)

    java_data = get_java_details(JAVA_XML_PATH)
    cpp_data = get_cpp_details(CPP_XML_PATH)

    m_url = f"https://sonarcloud.io/api/measures/component?component={SONAR_PROJECT_KEY}&metricKeys=coverage,bugs,code_smells,uncovered_lines,vulnerabilities"
    i_url = f"https://sonarcloud.io/api/issues/search?componentKeys={SONAR_PROJECT_KEY}&resolved=false&ps=10"
    
    sonar_measures = fetch_from_sonar(m_url)
    sonar_issues = fetch_from_sonar(i_url)

    unified_report = {
        "report_metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project_key": SONAR_PROJECT_KEY,
            "overall_status": "Success"
        },
        "coverage_summary": {
            "java_jacoco": java_data.get("language_coverage"),
            "cpp_gcovr": cpp_data.get("language_coverage")
        },
        "local_analysis": {
            "java_detailed": java_data,
            "cpp_detailed": cpp_data
        },
        "sonar_cloud_data": {
            "measures": sonar_measures.get('component', {}).get('measures', []),
            "unresolved_issues_count": sonar_issues.get('total', 0),
            "top_issues": sonar_issues.get('issues', [])
        }
    }

    with open("unified_master_report.json", "w") as f:
        json.dump(unified_report, f, indent=4)
    print("Report Generated Successfully!")

if __name__ == "__main__":
    main()
