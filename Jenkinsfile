pipeline {
  agent any

  environment {
        GIT_NAME = "eea.api.dataconnector"
        SONARQUBE_TAGS = "biodiversity.europa.eu,demo-biodiversity.eea.europa.eu,demo-www.eea.europa.eu,www.eea.europa.eu-en,forest.eea.europa.eu,industry.eea.europa.eu,insitu.copernicus.eu,demo-ied.eea.europa.eu,www.ied.eea.europa.eu-en,demo-water.devel5cph.eea.europa.eu-freshwater,water.europa.eu-freshwater"
    }

  stages {

    stage('Cosmetics') {
      steps {
        parallel(

          "JS Hint": {
            node(label: 'docker') {
              script {
                sh '''docker run -i --rm --name="$BUILD_TAG-jshint" -e GIT_SRC="https://github.com/eea/$GIT_NAME.git" -e GIT_NAME="$GIT_NAME" -e GIT_BRANCH="$BRANCH_NAME" -e GIT_CHANGE_ID="$CHANGE_ID" eeacms/jshint'''
              }
            }
          },

          "CSS Lint": {
            node(label: 'docker') {
              script {
                sh '''docker run -i --rm --name="$BUILD_TAG-csslint" -e GIT_SRC="https://github.com/eea/$GIT_NAME.git" -e GIT_NAME="$GIT_NAME" -e GIT_BRANCH="$BRANCH_NAME" -e GIT_CHANGE_ID="$CHANGE_ID" eeacms/csslint'''
              }
            }
          },

          "Ruff": {
            node(label: 'docker') {
              script {
                fix_result = sh(script: '''docker run --pull=always -i --rm --name="$BUILD_TAG-ruff-fix" -e GIT_SRC="https://github.com/eea/$GIT_NAME.git" -e GIT_NAME="$GIT_NAME" -e GIT_BRANCH="$BRANCH_NAME" -e GIT_CHANGE_ID="$CHANGE_ID" eeacms/ruff format''', returnStatus: true)
                sh '''docker cp $BUILD_TAG-ruff-fix:/code/$GIT_SRC .'''
                sh '''docker rm -v $BUILD_TAG-ruff-fix'''
                FOUND_FIX = sh(script: '''git diff | wc -l''', returnStdout: true).trim()

                if (FOUND_FIX != '0') {
                  withCredentials([string(credentialsId: 'eea-jenkins-token', variable: 'GITHUB_TOKEN')]) {
                    sh '''sed -i "s|url = .*|url = https://eea-jenkins:$GITHUB_TOKEN@github.com/eea/$GIT_NAME.git|" .git/config'''
                  }
                  sh '''git fetch origin $GIT_BRANCH:$GIT_BRANCH'''
                  sh '''git checkout $GIT_BRANCH'''
                  sh '''git add .'''
                  sh '''git commit -m "style: Automated code fix" '''
                  sh '''git push --set-upstream origin $GIT_BRANCH'''
                  sh '''exit 1'''
                }
              }
            }
          },
        )
      }
    }

    stage('Code') {
      steps {
        parallel(

          "ZPT Lint": {
            node(label: 'docker') {
              sh '''docker run -i --rm --name="$BUILD_TAG-zptlint" -e GIT_BRANCH="$BRANCH_NAME" -e ADDONS="$GIT_NAME" -e DEVELOP="src/$GIT_NAME" -e GIT_CHANGE_ID="$CHANGE_ID" eeacms/plone-test:4 zptlint'''
            }
          },

          "JS Lint": {
            node(label: 'docker') {
              sh '''docker run -i --rm --name="$BUILD_TAG-jslint" -e GIT_SRC="https://github.com/eea/$GIT_NAME.git" -e GIT_NAME="$GIT_NAME" -e GIT_BRANCH="$BRANCH_NAME" -e GIT_CHANGE_ID="$CHANGE_ID" eeacms/jslint4java'''
            }
          },

          "Ruff": {
            node(label: 'docker') {
              script {
                fix_result = sh(script: '''docker run --pull=always -i --rm --name="$BUILD_TAG-ruff-fix" -e GIT_SRC="https://github.com/eea/$GIT_NAME.git" -e GIT_NAME="$GIT_NAME" -e GIT_BRANCH="$BRANCH_NAME" -e GIT_CHANGE_ID="$CHANGE_ID" eeacms/ruff check''', returnStatus: true)
                sh '''docker cp $BUILD_TAG-ruff-fix:/code/$GIT_SRC .'''
                sh '''docker rm -v $BUILD_TAG-ruff-fix'''
                FOUND_FIX = sh(script: '''git diff | wc -l''', returnStdout: true).trim()

                if (FOUND_FIX != '0') {
                  withCredentials([string(credentialsId: 'eea-jenkins-token', variable: 'GITHUB_TOKEN')]) {
                    sh '''sed -i "s|url = .*|url = https://eea-jenkins:$GITHUB_TOKEN@github.com/eea/$GIT_NAME.git|" .git/config'''
                  }
                  sh '''git fetch origin $GIT_BRANCH:$GIT_BRANCH'''
                  sh '''git checkout $GIT_BRANCH'''
                  sh '''git add .'''
                  sh '''git commit -m "lint: Automated code fix" '''
                  sh '''git push --set-upstream origin $GIT_BRANCH'''
                  sh '''exit 1'''
                }
              }
            }
          },

          "i18n": {
            node(label: 'docker') {
              sh '''docker run -i --rm --name=$BUILD_TAG-i18n -e GIT_SRC="https://github.com/eea/$GIT_NAME.git" -e GIT_NAME="$GIT_NAME" -e GIT_BRANCH="$BRANCH_NAME" -e GIT_CHANGE_ID="$CHANGE_ID" eeacms/i18ndude'''
            }
          }
        )
      }
    }


    stage('Tests') {
      steps {
        parallel(

          "Plone5 & Python3": {
            node(label: 'docker') {
              sh '''docker pull eeacms/plone-test:5-python3; docker run -i --rm --name="$BUILD_TAG-plone5py3" -e GIT_BRANCH="$BRANCH_NAME" -e ADDONS="$GIT_NAME[test]" -e DEVELOP="src/$GIT_NAME" -e GIT_CHANGE_ID="$CHANGE_ID" eeacms/plone-test:5-python3 -v -vv -s $GIT_NAME'''
            }
          },
        )
      }
    }


    stage('Report to SonarQube') {
      when {
        allOf {
          environment name: 'CHANGE_ID', value: ''
        }
      }
      steps {
        node(label: 'swarm') {
          script{
            checkout scm
            // dir("xunit-reports") {
            //   unstash "xunit-reports"
            // }
            // unstash "coverage.xml"
            def scannerHome = tool 'SonarQubeScanner';
            def nodeJS = tool 'NodeJS11';
            withSonarQubeEnv('Sonarqube') {
                // sh '''sed -i "s|/plone/instance/src/$GIT_NAME|$(pwd)|g" coverage.xml'''
                sh "export PATH=$PATH:${scannerHome}/bin:${nodeJS}/bin; sonar-scanner -Dsonar.python.xunit.skipDetails=true -Dsonar.python.xunit.reportPath=xunit-reports/*.xml -Dsonar.python.coverage.reportPaths=coverage.xml -Dsonar.sources=./eea -Dsonar.projectKey=$GIT_NAME-$BRANCH_NAME -Dsonar.projectVersion=$BRANCH_NAME-$BUILD_NUMBER"
                sh '''try=2; while [ \$try -gt 0 ]; do curl -s -XPOST -u "${SONAR_AUTH_TOKEN}:" "${SONAR_HOST_URL}api/project_tags/set?project=${GIT_NAME}-${BRANCH_NAME}&tags=${SONARQUBE_TAGS},${BRANCH_NAME}" > set_tags_result; if [ \$(grep -ic error set_tags_result ) -eq 0 ]; then try=0; else cat set_tags_result; echo "... Will retry"; sleep 60; try=\$(( \$try - 1 )); fi; done'''
            }
          }
        }
      }
    }

    stage('Pull Request') {
      when {
        not {
          environment name: 'CHANGE_ID', value: ''
        }
        environment name: 'CHANGE_TARGET', value: 'master'
      }
      steps {
        node(label: 'docker') {
          script {
            if ( env.CHANGE_BRANCH != "develop" &&  !( env.CHANGE_BRANCH.startsWith("hotfix")) ) {
                error "Pipeline aborted due to PR not made from develop or hotfix branch"
            }
           withCredentials([string(credentialsId: 'eea-jenkins-token', variable: 'GITHUB_TOKEN')]) {
            sh '''docker run -i --rm --name="$BUILD_TAG-gitflow-pr" -e GIT_CHANGE_BRANCH="$CHANGE_BRANCH" -e GIT_CHANGE_AUTHOR="$CHANGE_AUTHOR" -e GIT_CHANGE_TITLE="$CHANGE_TITLE" -e GIT_TOKEN="$GITHUB_TOKEN" -e GIT_BRANCH="$BRANCH_NAME" -e GIT_CHANGE_ID="$CHANGE_ID" -e GIT_ORG="$GIT_ORG" -e GIT_NAME="$GIT_NAME" eeacms/gitflow'''
           }
          }
        }
      }
    }

    stage('Release') {
      when {
        allOf {
          environment name: 'CHANGE_ID', value: ''
          branch 'master'
        }
      }
      steps {
        node(label: 'docker') {
          withCredentials([[$class: 'UsernamePasswordMultiBinding', credentialsId: 'eea-jenkins', usernameVariable: 'EGGREPO_USERNAME', passwordVariable: 'EGGREPO_PASSWORD'],string(credentialsId: 'eea-jenkins-token', variable: 'GITHUB_TOKEN'),[$class: 'UsernamePasswordMultiBinding', credentialsId: 'pypi-jenkins', usernameVariable: 'PYPI_USERNAME', passwordVariable: 'PYPI_PASSWORD']]) {
            sh '''docker run -i --rm --name="$BUILD_TAG-gitflow-master" -e GIT_BRANCH="$BRANCH_NAME" -e EGGREPO_USERNAME="$EGGREPO_USERNAME" -e EGGREPO_PASSWORD="$EGGREPO_PASSWORD" -e GIT_NAME="$GIT_NAME"  -e PYPI_USERNAME="$PYPI_USERNAME"  -e PYPI_PASSWORD="$PYPI_PASSWORD" -e GIT_ORG="$GIT_ORG" -e GIT_TOKEN="$GITHUB_TOKEN" eeacms/gitflow'''
          }
        }
      }
    }

  }

  post {
    changed {
      script {
        def url = "${env.BUILD_URL}/display/redirect"
        def status = currentBuild.currentResult
        def subject = "${status}: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]'"
        def summary = "${subject} (${url})"
        def details = """<h1>${env.JOB_NAME} - Build #${env.BUILD_NUMBER} - ${status}</h1>
                         <p>Check console output at <a href="${url}">${env.JOB_BASE_NAME} - #${env.BUILD_NUMBER}</a></p>
                      """

        def color = '#FFFF00'
        if (status == 'SUCCESS') {
          color = '#00FF00'
        } else if (status == 'FAILURE') {
          color = '#FF0000'
        }

        emailext (subject: '$DEFAULT_SUBJECT', to: '$DEFAULT_RECIPIENTS', body: details)
      }
    }
  }
}
