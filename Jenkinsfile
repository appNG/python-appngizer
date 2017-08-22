node {
  try {
    // Set and use lowercased branch name
    def branch_name = env.BRANCH_NAME.toLowerCase()

    // Set aptly repository to publish depending on branch name
    def aptly_repo = 'appng_experimental'
    def aptly_dist = 'experimental'
    if (branch_name == 'master') {
      aptly_repo = 'appng_stable'
      aptly_dist = 'stable'
    }
    if (branch_name == 'develop') {
      aptly_repo = 'appng_unstable'
      aptly_dist = 'unstable'
    }
    // Set and debianize branch_name as version component
    def git_branch_name = branch_name.replace(/\W/,".")
    
    stage ('notifyStart'){
      emailext (
          subject: "[appNG Jenkins] STARTED: Job ${env.JOB_NAME} [${env.BUILD_NUMBER}]",
          body: """<p>STARTED: Job <strong>${env.JOB_NAME} [${env.BUILD_NUMBER}]</strong>:</p>
              <p>Check console output at <a href="${env.BUILD_URL}console">${env.BUILD_URL}console</a></p>""",
          recipientProviders: [[$class: 'DevelopersRecipientProvider'], [$class: 'RequesterRecipientProvider']],
          mimeType: 'text/html'
      )
    }
    
    stage('Cleanup dist directories before build') {
      sh "rm -rf dist/* deb_dist/*"
    }
    
    stage ('Checkout'){
      git branch: '$BRANCH_NAME', url: 'https://github.com/appNG/python-appngizer.git'
    }
    
    // Determine version from setuptools_scm
    def st_version = sh (returnStdout: true, script: '/usr/bin/python2.7 setup.py --version').trim()
    def st_version_components = st_version.tokenize('.')
    def st_version_sem = st_version_components[0,1,2].join('.')
    
    stage('Setuptools clean build docs') {
      sh "mkdir -p docs/build"
      sh "/usr/bin/python2.7 setup.py clean build docs"
    }
    
    stage('Copy docs to appng.org docroot') {
      dir("docs/build/html"){
        def www_docroot = '/srv/www/appng.org/python-appngizer'
        def doc_dir = www_docroot + '/' + st_version_sem

        if ( branch_name == 'master' ) {
          //start with a clean directory
          sh "rm -rf '${doc_dir}'"
          sh "mkdir -p '${doc_dir}'"
          // copy documentation
          sh "cp -R * '${doc_dir}'"
        } else {
          //start with a clean directory
          sh "rm -rf '${doc_dir}-${git_branch_name}'"
          sh "mkdir -p '${doc_dir}-${git_branch_name}'"
          // copy documentation
          sh "cp -R * '${doc_dir}-${git_branch_name}'"
        }
      }
    }
    
    stage('Setuptools create sdist and bdist_wheel') {
      sh "/usr/bin/python2.7 setup.py sdist"
      sh "/usr/bin/python2.7 setup.py bdist_wheel --universal"
    }
    
    stage('Setuptools create source debian packages') {
      // If branch isnt master, head(tag), develop we add 
      // branch_name as debian upstream version suffix
      if ( ['master','head','develop'].contains(branch_name) ) {
        sh "/usr/bin/python2.7 setup.py --command-packages=stdeb.command sdist_dsc"
      } else {
        sh "/usr/bin/python2.7 setup.py --command-packages=stdeb.command sdist_dsc --upstream-version-suffix '.$git_branch_name'"
      }
    }
    
    stage('Setuptools create binary debian packages') {
      sh "cd deb_dist/appngizer*/; dpkg-buildpackage -rfakeroot -b -uc"
    }
    
    stage('Publish to aptly repository'){
      sh "sudo -H -u aptly '/usr/bin/aptly' repo add -force-replace=true $aptly_repo ./deb_dist/*.deb"
      sh "sudo -H -u aptly '/usr/bin/aptly' publish update -force-overwrite=true $aptly_dist prod"
    }

    if ( branch_name == 'master' ) {
      // Check if version already exist
      def pypi_url = 'https://pypi.python.org/pypi/appngizer/' + st_version_sem
      def pypi_http_status = sh (returnStdout: true, script: "curl -s --head -w %{http_code} ${pypi_url} -o /dev/null").trim()
      
      if ( pypi_http_status == '404' ) {
        stage('Publish to pypi'){
          sh "twine upload dist/*"
        }
      }
    }
    
    currentBuild.result = 'SUCCESS'
    
    stage ('notifyFinish'){
      // send to email
      emailext (
        subject: "[appNG Jenkins] FINISHED: Job ${env.JOB_NAME} [${env.BUILD_NUMBER}] with status: ${currentBuild.result}",
        body: """<p>FINISHED: Job <strong>${env.JOB_NAME} [${env.BUILD_NUMBER}]</strong> with status: <strong>${currentBuild.result}</strong></p>
            <p>Check console output at <a href="${env.BUILD_URL}">${env.BUILD_URL}</a></p>""",
        recipientProviders: [[$class: 'DevelopersRecipientProvider'], [$class: 'RequesterRecipientProvider']],
        mimeType: 'text/html'
      )
    }
  } catch (Exception err) {
    currentBuild.result = 'FAILURE'
    throw err
  }
}
