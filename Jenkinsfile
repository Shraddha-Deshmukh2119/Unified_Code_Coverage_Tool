pipeline {
    agent any
    tools {
        maven 'maven'
        jdk   'JDK25' 
    }

    parameters {
        choice(name: 'REPO_MODE', choices: ['SINGLE_REPO', 'SEPARATE_REPOS'], description: 'Choose your repository structure')
        string(name: 'COMBINED_REPO_URL', defaultValue: '', description: 'URL for single repo')
        string(name: 'JAVA_REPO_URL', defaultValue: '', description: 'Java repo URL')
        string(name: 'CPP_REPO_URL', defaultValue: '', description: 'C++ repo URL')
        string(name: 'SCRIPT_PATH', defaultValue: 'D:\\jenkins-scripts\\unify_reports.py', description: 'Path to Python script')
        string(name: 'SONAR_ORG_KEY', defaultValue: '', description: 'SonarCloud Org')
        string(name: 'SONAR_PROJECT_KEY', defaultValue: '', description: 'SonarCloud Project')
    }

    environment {
        SONAR_TOKEN = credentials('SonarCloud-token')
        SONAR_PROJECT_KEY = "${params.SONAR_PROJECT_KEY}"
        SONAR_ORG_KEY = "${params.SONAR_ORG_KEY}"
    }

    stages {
        stage('Checkout') {
            steps {
                cleanWs()
                script {
                    if (params.REPO_MODE == 'SINGLE_REPO') {
                        checkout scm: [$class: 'GitSCM', branches: [[name: '*/main']], userRemoteConfigs: [[url: params.COMBINED_REPO_URL]]]
                        env.JAVA_BASE = fileExists('java-project') ? 'java-project' : '.'
                        env.CPP_BASE  = fileExists('cpp-project') ? 'cpp-project' : '.'
                    } else {
                        dir('java-app') { checkout scm: [$class: 'GitSCM', branches: [[name: '**']], userRemoteConfigs: [[url: params.JAVA_REPO_URL]]] }
                        dir('cpp-app') { checkout scm: [$class: 'GitSCM', branches: [[name: '**']], userRemoteConfigs: [[url: params.CPP_REPO_URL]]] }
                        env.JAVA_BASE = 'java-app'
                        env.CPP_BASE = 'cpp-app'
                    }
                    env.RUN_JAVA = (env.JAVA_BASE && fileExists("${env.JAVA_BASE}/pom.xml")) ? 'true' : 'false'
                    env.RUN_CPP  = (env.CPP_BASE && (fileExists("${env.CPP_BASE}/bank.cpp") || fileExists("${env.CPP_BASE}/main.cpp"))) ? 'true' : 'false'
                }
            }
        }

        stage('Build & Test') {
            parallel {
                stage('Java') {
                    when { expression { env.RUN_JAVA == 'true' } }
                    steps { dir(env.JAVA_BASE) { bat" mvn clean verify -U -Dmaven.repo.local=.m2/repository" } }
                }
                stage('C++') {
                    when { expression { env.RUN_CPP == 'true' } }
                    steps {
                        dir(env.CPP_BASE) {
                            bat 'python -m venv venv && venv\\Scripts\\pip install gcovr'
                            bat 'curl -LsS https://sonarcloud.io/static/cpp/build-wrapper-win-x86.zip -o bw.zip && powershell Expand-Archive bw.zip . -Force'
                            bat """
                            .\\build-wrapper-win-x86\\build-wrapper-win-x86-64.exe --out-dir bw-output g++ --coverage *.cpp -o runner.exe
                            runner.exe
                            venv\\Scripts\\python.exe -m gcovr --sonarqube -o cpp-coverage.xml --root ..
                            """
                        }
                    }
                }
            }
        }

      stage('Sonar Scan') {
    steps {
        script {
            def scanner = tool name: 'sonar_scanner', type: 'hudson.plugins.sonar.SonarRunnerInstallation'
            def src = []
            if (env.RUN_JAVA == 'true') src << "${env.JAVA_BASE}/src/main"
            if (env.RUN_CPP == 'true')  src << "${env.CPP_BASE}"

            withSonarQubeEnv('SonarCloud-token') {
                bat """
                "${scanner}\\bin\\sonar-scanner" ^
                -Dsonar.userHome="${WORKSPACE}\\.sonar" ^
                -Dsonar.projectKey=${SONAR_PROJECT_KEY} ^
                -Dsonar.organization=${SONAR_ORG_KEY} ^
                -Dsonar.sources=${src.join(',')} ^
                -Dsonar.exclusions=**/venv/**,**/target/**,**/*.js,**/*.css ^
                -Dsonar.java.binaries=**/target/classes ^
                -Dsonar.coverage.jacoco.xmlReportPaths=**/target/site/jacoco/jacoco.xml ^
                -Dsonar.cfamily.build-wrapper-output=${env.CPP_BASE}/bw-output ^
                -Dsonar.coverageReportPaths=${env.CPP_BASE}/cpp-coverage.xml ^
                -Dsonar.scm.disabled=true
                """
            }
        }
    }
}

        stage('Final Reporting') {
            steps {
                script {
                    echo "Processing reports..."
                    sleep 45
                    env.JAVA_XML_PATH = "${env.JAVA_BASE}/target/site/jacoco/jacoco.xml"
                    env.CPP_XML_PATH  = "${env.CPP_BASE}/cpp-coverage.xml"
                    
                    withEnv([
                        "JAVA_XML_PATH=${env.JAVA_XML_PATH}",
                        "CPP_XML_PATH=${env.CPP_XML_PATH}"
                    ]) {
                        bat "python \"${params.SCRIPT_PATH}\""
                    }
                    archiveArtifacts 'unified_master_report.json'
                }
            }
        }
    }
}
