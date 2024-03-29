var addonName = null
var addonVersion = null
var accessToken = null
var projectName = null
var addonScope = null
var addonSettings = null
var sgAccessToken = null
var ayonAPI = null

const init = () => {
 /* When the addon page is loaded, it receive a message with context and
  additional data (accessToken, addon version...). When the context is changed,
  a message is re-broadcasted, so the page can react to changes in selection etc.  */

  window.onmessage = async (e) => {
    const context = e.data.context
    addonName = e.data.addonName
    addonVersion = e.data.addonVersion
    accessToken = e.data.accessToken
    addonScope = e.data.scope

    ayonAPI = axios.create({
      baseUrl: `${e.origin}/api/`,
      headers: {"Authorization": `Bearer ${accessToken}`}
    })

    addonSettings = await ayonAPI
      .get(`/api/addons/${addonName}/${addonVersion}/settings`)
      .then((result) => result.data);

    addonSecrets = await ayonAPI
      .get(`/api/secrets/${addonSettings.shotgrid_api_secret}`)
      .then((result) => result.data);

    addonSettings.shotgrid_script_name = addonSecrets.name
    addonSettings.shotgrid_api_key = addonSecrets.value
  } // end of window.onmessage
} // end of init

const populateTable = async () => {
  /* Get all the projects from AYON and Shotgrid, then populate the table with their info
  and a button to Syncronize if they pass the requirements */
  ayonProjects = await getAyonProjects();
  sgProjects = await getShotgridProjects();

  var allProjects = ayonProjects

  sgProjects.forEach((sg_project) => {
    let already_exists = false
    allProjects.forEach((project) => {
      if (sg_project.name == project.ayonId) {
          already_exists = true
          project.shotgridId = sg_project.shotgridId
      }
    })
    if (!already_exists) {
      sg_project.ayonId = null
      allProjects.push(sg_project)
    }
  })

  allProjects.sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()));

  const ProjectsTable = document.getElementById("sg-addon-projects-table")
  const ProjectsTableHeader = document.getElementById("sg-addon-projects-table-header")
  const ProjectsTableBody = document.getElementById("sg-addon-projects-table")
  ProjectsTableBody.innerHTML = '';
  ProjectsTableBody.appendChild(ProjectsTableHeader);

  allProjects.forEach((project) => {
    var tableRow = document.createElement('tr')

    var nameCell = document.createElement('td')
    nameCell.innerText = project.name
    tableRow.appendChild(nameCell)

    var codeCell = document.createElement('td')
    codeCell.innerText = project.code
    tableRow.appendChild(codeCell)

    var ayonCell = document.createElement('td')
    ayonCell.innerText = project.ayonId ? 'Yes' : 'No';
    tableRow.appendChild(ayonCell)

    var sgCell = document.createElement('td')
    sgCell.innerText = project.shotgridId ? 'Yes' : 'No';
    tableRow.appendChild(sgCell)

    var syncCell = document.createElement('td')

    var sgSyncButton = document.createElement('button')
    sgSyncButton.innerText = `Shotgrid -> AYON`
    sgSyncButton.disabled = true;

    if (project.shotgridId && project.code) {
      if (/^["a-zA-Z0-9_"]{1,32}/.test(project.name) && /^[a-zA-Z][a-zA-Z0-9]+/.test(project.code)) {
        // Only Enable button if its a valid name and code
        sgSyncButton.disabled = false;
        sgSyncButton.setAttribute("data-ayon-name", project.name);
        sgSyncButton.setAttribute("data-ayon-code", project.code);

        sgSyncButton.addEventListener('click', function () {
          syncShotgridToAyon(this.attributes["data-ayon-name"].value, this.attributes["data-ayon-code"].value)
        }, false);
      }
    }
    syncCell.appendChild(sgSyncButton)

    var ayonSyncButton = document.createElement('button')
    ayonSyncButton.innerText = `AYON -> Shotgrid`
    ayonSyncButton.disabled = project.ayonId ? false : true;
    ayonSyncButton.setAttribute("data-ayon-name", project.name);
    ayonSyncButton.setAttribute("data-ayon-code", project.code);
    ayonSyncButton.addEventListener('click', function () {
          syncAyonToShotgrid(this.attributes["data-ayon-name"].value, this.attributes["data-ayon-code"].value)
        }, false);
    syncCell.appendChild(ayonSyncButton)

    tableRow.appendChild(syncCell)

    ProjectsTableBody.appendChild(tableRow)
  });
}


const syncUsers = async () => {
  /* Get all the Users from AYON and Shotgrid, then populate the table with their info
  and a button to Synchronize if they pass the requirements */
  ayonUsers = await getAyonUsers();
  sgUsers = await getShotgridUsers();

  sgUsers.forEach((sg_user) => {
    let already_exists = false
    ayonUsers.forEach((user) => {
      if (sg_user.login == user.name) {
          already_exists = true
      }
    })
    if (!already_exists) {
      createNewUserInAyon(sg_user.login, sg_user.email, sg_user.name)
    }
  })
}


const getShotgridUsers = async () => {
  /* Query Shotgrid for all active users. */
  const sgBaseUrl = `${addonSettings.shotgrid_server.replace(/\/+$/, '')}/api/v1`
  sgAuthToken = await axios
    .post(`${sgBaseUrl}/auth/access_token`, {
        client_id: addonSettings.shotgrid_script_name,
        client_secret: addonSettings.shotgrid_api_key,
        grant_type: "client_credentials",
    }, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
      }
    })
    .then((result) => result.data.access_token)
    .catch((error) => {
      console.log("Unable to Acquire the Shotgrid Authorization Token!")
      console.log(error)
    });

    sgUsers = await axios
      .get(`${sgBaseUrl}/entity/human_users?fields=*`, {
        headers: {
            'Authorization': `Bearer ${sgAuthToken}`,
            'Accept': 'application/json'
        }
      })
      .then((result) => result.data.data)
      .catch((error) => {
        console.log("Unable to Fetch Shotgrid Users!")
        console.log(error)
      });

    var sgUsersConformed = []
    
    users_to_ignore = ["dummy", "root", "support"]
    if (sgUsers) {
      sgUsers.forEach((sg_user) => {
        if (
          sg_user.attributes.sg_status_list == "act" &&
          !users_to_ignore.some(item => sg_user.attributes.email.includes(item))
        ) {
          sgUsersConformed.push({
            "login": sg_user.attributes.login,
            "name": sg_user.attributes.name,
            "email": sg_user.attributes.email,
          })
        }
      });
    }
    return sgUsersConformed;
}


const getAyonUsers = async () => {
  /* Query AYON for all existing users. */
  ayonUsers = await axios({
    url: '/graphql',
    headers: {"Authorization": `Bearer ${accessToken}`},
    method: 'post',
    data: {
      query: `
        query ActiveUsers {
          users {
            edges {
              node {
                attrib {
                  email
                  fullName
                }
                active
                name
              }
            }
          }
        }
        `
    }
  }).then((result) => result.data.data.users.edges);

  var ayonUsersConformed = []

  if (ayonUsers) {
    ayonUsers.forEach((user) => {
      ayonUsersConformed.push({
        "name": user.node.name,
        "email": user.node.attrib.email,
        "fullName": user.node.attrib.fullName,
      })
    })
  }
    return ayonUsersConformed
}


const createNewUserInAyon = async (login, email, name) => {
  call_result_paragraph = document.getElementById("call-result");

  response = await ayonAPI
    .put("/api/users/" + login, {
      "active": true,
      "attrib": {
        "fullName": name,
        "email": email,
      },
      "password": login,
    })
    .then((result) => result)
    .catch((error) => {
      console.log("Unable to create user in AYON!")
      console.log(error)
      call_result_paragraph.innerHTML = `Unable to create user in AYON! ${error}`
  });
}


const getShotgridProjects = async () => {
  /* Query Shotgrid for all existing projects. */
  const sgBaseUrl = `${addonSettings.shotgrid_server.replace(/\/+$/, '')}/api/v1`
  sgAuthToken = await axios
    .post(`${sgBaseUrl}/auth/access_token`, {
        client_id: addonSettings.shotgrid_script_name,
        client_secret: addonSettings.shotgrid_api_key,
        grant_type: "client_credentials",
    }, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
      }
    })
    .then((result) => result.data.access_token)
    .catch((error) => {
      console.log("Unable to Acquire the Shotgrid Authorization Token!")
      console.log(error)
    });

  sgProjects = await axios
    .get(`${sgBaseUrl}/entity/projects?fields=*`, {
      headers: {
        'Authorization': `Bearer ${sgAuthToken}`,
        'Accept': 'application/json'
      }
    })
    .then((result) => result.data.data)
    .catch((error) => {
      console.log("Unable to Fetch Shotgrid Projects!")
      console.log(error)
    });

  var sgProjectsConformed = []

  if (sgProjects) {
    sgProjects.forEach((project) => {
      sgProjectsConformed.push({
        "name": project.attributes.name,
        "code": project.attributes[`${addonSettings.shotgrid_project_code_field}`],
        "shotgridId": project.id,
        "ayonId": project.attributes.sg_ayon_id,
      })
    });
  }
  return sgProjectsConformed;
}

const getAyonProjects = async () => {
  /* Query AYON for all existing projects. */
  ayonProjects = await axios({
    url: '/graphql',
    headers: {"Authorization": `Bearer ${accessToken}`},
    method: 'post',
    data: {
      query: `
        query ActiveProjects {
          projects {
            edges {
              node {
                attrib {
                  shotgridId
                }
                active
                code
                name
              }
            }
          }
        }
        `
    }
  }).then((result) => result.data.data.projects.edges);

  var ayonProjectsConformed = []

  if (ayonProjects) {
    ayonProjects.forEach((project) => {
      ayonProjectsConformed.push({
        "name": project.node.name,
        "code": project.node.code,
        "shotgridId": project.node.attrib.shotgridId,
        "ayonId": project.node.name,
      })
    })
  }
    return ayonProjectsConformed
}


const syncShotgridToAyon = async (projectName, projectCode) => {
  /* Spawn an AYON Event of topic "shotgrid.event" to synchcronize a project
  from Shotgrid into AYON. */
  call_result_paragraph = document.getElementById("call-result");

  dispatch_event = await ayonAPI
    .post("/api/events", {
      "topic": "shotgrid.event",
      "project": projectName,
      "description": `Synchronize Project ${projectName} from Shotgrid.`,
      "payload": {
        "action": "sync-from-shotgrid",
        "project_name": projectName,
        "project_code": projectCode,
        "project_code_field": addonSettings.shotgrid_project_code_field,
      },
      "finished": true,
      "store": true
    })
    .then((result) => result)
    .catch((error) => {
      console.log("Unable to submit event to AYON!")
      console.log(error)
      call_result_paragraph.innerHTML = `Unable to submit event to AYON! ${error}`
    });

  if (dispatch_event) {
    call_result_paragraph.innerHTML = `Succesfully Spawned Event! ${dispatch_event.data.id}`
  }
}

const syncAyonToShotgrid = async (projectName, projectCode) => {
  /* Spawn an AYON Event of topic "shotgrid.event" to synchcronize a project
  from AYON into Shotgrid. */
  call_result_paragraph = document.getElementById("call-result");

  dispatch_event = await ayonAPI
    .post("/api/events", {
      "topic": "shotgrid.event",
      "project": projectName,
      "description": `Synchronize Project ${projectName} from AYON.`,
      "payload": {
        "action": "sync-from-ayon",
        "project_name": projectName,
        "project_code": projectCode,
        "project_code_field": addonSettings.shotgrid_project_code_field,
      },
      "finished": true,
      "store": true
    })
    .then((result) => result)
    .catch((error) => {
      console.log("Unable to submit event to AYON!")
      console.log(error)
      call_result_paragraph.innerHTML = `Unable to submit event to AYON! ${error}`
    });

  if (dispatch_event) {
    call_result_paragraph.innerHTML = `Succesfully Spawned Event! ${dispatch_event.data.id} Make sure there's a processor <a target="_parent" href="/services">Service running</a>`
  }
}

document.addEventListener('DOMContentLoaded', () => {
 init()
})
