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
      .get(`/api/secrets/${addonSettings.service_settings.script_key}`)
      .then((result) => result.data);

    addonSettings.shotgrid_api_key = addonSecrets.value
  } // end of window.onmessage
} // end of init

const populateTable = async () => {
  /* Get all the projects from AYON and Shotgrid, then populate the table with their info
  and a button to Synchronize if they pass the requirements */
  ayonProjects = await getAyonProjects();
  sgProjects = await getShotgridProjects();

  var allProjects = ayonProjects

  sgProjects.forEach((sg_project) => {
    let already_exists = false
    allProjects.forEach((project) => {
      if (sg_project.name == project.ayonId) {
          already_exists = true
          project.shotgridId = sg_project.shotgridId
          project.sg_ayon_auto_sync = sg_project.sg_ayon_auto_sync
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

    // undefined == project does not exist in AYON
    // false == project inactive in AYON
    // true == project active in AYON
    if (project.active == false) { 
      return ; 
    }
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
    sgSyncButton.innerText = `Flow ► AYON`
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
    ayonSyncButton.innerText = `AYON ► Flow`
    ayonSyncButton.disabled = project.ayonId ? false : true;
    ayonSyncButton.setAttribute("data-ayon-name", project.name);
    ayonSyncButton.setAttribute("data-ayon-code", project.code);
    ayonSyncButton.addEventListener('click', function () {
          syncAyonToShotgrid(this.attributes["data-ayon-name"].value, this.attributes["data-ayon-code"].value)
        }, false);
    syncCell.appendChild(ayonSyncButton)

    tableRow.appendChild(syncCell)

    var autoSyncCell = document.createElement('td')
    autoSyncCell.innerText = ""
    if (ayonCell.innerText == "Yes" && sgCell.innerText == "Yes")
    {
        if (project.shotgridPush && project.sg_ayon_auto_sync) {
          autoSyncCell.innerText = "Syncing both ways AYON <-> Flow";
        }
        else{
          if (project.shotgridPush) {
            autoSyncCell.innerText = "Syncing only from AYON to Flow";
          }
          else {
            if (project.sg_ayon_auto_sync) {
              autoSyncCell.innerText = "Syncing only from Flow to AYON";
            }
          }
        }
    }
    tableRow.appendChild(autoSyncCell)

    ProjectsTableBody.appendChild(tableRow)
  });
}


const syncUsers = async () => {
  /* Get all the Users from AYON and Shotgrid, then populate the table with their info
  and a button to Synchronize if they pass the requirements */
  ayonUsers = await getAyonUsers();
  sgUsers = await getShotgridUsers();

  let new_users = []

  for (const sg_user of sgUsers) {
    const ayonUser = await getAyonUserFromShotgridId(sg_user.id)
    if (typeof ayonUser === "string" && ayonUser.trim() !== "") {
      console.log("sg_user already exists.")
    }
    else {
        // make sure no @ and validate login string
        let ay_fixed_login = validateLogin(sg_user.login);
        let login_already_exists = false;

        ayonUsers.forEach((user) => {
          if (ay_fixed_login == user.name) {
              login_already_exists = true
          }
        })

        // User login exists in AYON but no associated sg_user_id.
        if (login_already_exists){
          updateUserInAyon(sg_user.id, sg_user.login)
        }

        // User login does not exist in AYON.
        else {
          createNewUserInAyon(
            sg_user.id, sg_user.login, sg_user.email, sg_user.name)
        }

      new_users.push(sg_user.name)
    }
  }

  call_result_paragraph = document.getElementById("call-result");
  if (new_users.length !== 0) {
    call_result_paragraph.innerHTML = `Added new users: ` + new_users.join(" ")
  }
  else{
    call_result_paragraph.innerHTML = `All users are already synced.`
  }
}


const getAyonUserFromShotgridId = async (sg_user_id) => {
  /* Query the AYON user matching provided Shotgrid Id. */
  ayon_user = await axios({
    url: `/api/addons/${addonName}/${addonVersion}/get_ayon_name_by_sg_id/${sg_user_id}`,
    headers: {"Authorization": `Bearer ${accessToken}`},
    method: 'get',
  }).then((result) => result.data);

  return ayon_user
}


const getShotgridUsers = async () => {
  /* Query Shotgrid for all active users. */
  const sgBaseUrl = `${addonSettings.shotgrid_server.replace(/\/+$/, '')}/api/v1`
  sgAuthToken = await axios
    .post(`${sgBaseUrl}/auth/access_token`, {
        client_id: `${addonSettings.service_settings.script_name}`,
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
      .get(`${sgBaseUrl}/entity/human_users?filter[sg_status_list]=act&fields=login,name,email`, {
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

    /* Do some extra clean up on the users returned. */
    var sgUsersConformed = []
    users_to_ignore = ["dummy", "root", "support"]
    if (sgUsers) {
      sgUsers.forEach((sg_user) => {
        if (
          !users_to_ignore.some(item => sg_user.attributes.email.includes(item))
        ) {
          sgUsersConformed.push({
            "id": sg_user.id,
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

function validateLogin(login) {
  // First sanitize by replacing @ with underscore
  let new_login = login.replace(/@/g, '_');

  // Ensure valid pattern
  const validPattern = /^[a-zA-Z0-9][a-zA-Z0-9_\.\-]*[a-zA-Z0-9]$/;

  if (!validPattern.test(new_login)) {
    // If invalid, create valid string by:
    // 1. Remove invalid chars
    // 2. Ensure starts/ends with alphanumeric
    let _new_login = new_login.replace(/[^a-zA-Z0-9_\.\-]/g, '')
      .replace(/^[^a-zA-Z0-9]+/, '')
      .replace(/[^a-zA-Z0-9]+$/, '');

    // If result too short, append 'user'
    if (_new_login.length < 2) {
      new_login = 'user' + _new_login;
    }
  }

  return new_login;
}

const updateUserInAyon = async (id, login) => {
  /* Update an existing AYON user to set its sg_user_id. */
  call_result_paragraph = document.getElementById("call-result");

  // make sure no @ and validate login string
  let fixed_login = validateLogin(login);

  response = await ayonAPI
    .patch("/api/users/" + fixed_login, {
      "data": {
        "sg_user_id": id
      },
    })
    .then((result) => result)
    .catch((error) => {
      console.log("Unable to update user in AYON!")
      console.log(error)
      call_result_paragraph.innerHTML = `Unable to update user in AYON! ${error}`
    });
}

const createNewUserInAyon = async (id, login, email, name) => {
  /* Create a new AYON user.*/
  call_result_paragraph = document.getElementById("call-result");

  // make sure no @ and validate login string
  let fixed_login = validateLogin(login);

  response = await ayonAPI
    .put("/api/users/" + fixed_login, {
      "active": true,
      "attrib": {
        "fullName": name,
        "email": email,
      },
      "data": {
        "sg_user_id": id
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
      client_id: `${addonSettings.service_settings.script_name}`,
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
      "sg_ayon_auto_sync": project.attributes.sg_ayon_auto_sync,
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
                  shotgridPush
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
        "shotgridPush": project.node.attrib.shotgridPush,
        "ayonId": project.node.name,
        "active": project.node.active,
      })
    })
  }
    return ayonProjectsConformed
}


const syncShotgridToAyon = async (projectName, projectCode) => {
  /* Spawn an AYON Event of topic "shotgrid.event.project.sync" to synchronize a project
  from Shotgrid into AYON. */
  call_result_paragraph = document.getElementById("call-result");

  dispatch_event = await ayonAPI
    .post("/api/events", {
      "topic": "shotgrid.event.project.sync",
      "project": projectName,
      "description": `Synchronize Project '${projectName}' from Shotgrid.`,
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
    call_result_paragraph.innerHTML = `Successfully Spawned Event! ${dispatch_event.data.id} Make sure there's a processor <a target="_parent" href="/services">Service running</a>`
  }
}

const syncAyonToShotgrid = async (projectName, projectCode) => {
  /* Spawn an AYON Event of topic "shotgrid.event.project.sync"
  to synchronize a project from AYON into Shotgrid. */
  call_result_paragraph = document.getElementById("call-result");

  dispatch_event = await ayonAPI
    .post("/api/events", {
      "topic": "shotgrid.event.project.sync",
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
    call_result_paragraph.innerHTML = `Successfully Spawned Event! ${dispatch_event.data.id} Make sure there's a processor <a target="_parent" href="/services">Service running</a>`
  }
}

document.addEventListener('DOMContentLoaded', () => {
 init()
})
