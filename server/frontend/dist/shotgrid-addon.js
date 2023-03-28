var addonName = null
var addonVersion = null
var accessToken = null
var projectName = null
var addonScope = null

const init = () => {
 /*
When the addon page is loaded, it receive a message with context and
additional data (accessToken, addon version...). When the context is changed, 
a message is re-broadcasted, so the page can react to changes in selection etc.
 */

  window.onmessage = (e) => {
    const context = e.data.context
    addonName = e.data.addonName
    addonVersion = e.data.addonVersion
    accessToken = e.data.accessToken
    addonScope = e.data.scope

    getSyncableProjects();
    getShotgridProjects();
  } // end of window.onmessage
} // end of init

const importProject = (projectName, projectCode) => {
  /* Trigger an event dispatching for a project creation/import.

    Given a `projectName` and `projectCode` make an API call to the custom API
    endpoint `create-project` which will create a `shotgrid.event` to be handled
    by any listening processor.
  */
  if (projectName) {
    const url = `/api/addons/${addonName}/${addonVersion}/create-project`
    const headers = {"Authorization": `Bearer ${accessToken}`}
    axios
      .post(url, data={"project_name": `${projectName}`, "project_code": `${projectCode}`}, {headers})
      .then((response) => {
        const msg = `Create response data: ${response.data}` 
        document.querySelector("#call-result").innerHTML = msg
      })
  }
}

const syncProject = (projectName) => {
  /* Trigger an event dispatching for a project syncronization.

    Given a `projectName` make an API call to the custom API endpoint
    `sync-from-shotgrid` which will create a `shotgrid.event` to be handled
    by any listening processor.
  */
  if (projectName) {
    const url = `/api/addons/${addonName}/${addonVersion}/sync-from-shotgrid/${projectName}`
    const headers = {"Authorization": `Bearer ${accessToken}`}

    axios
      .get(url, {headers})
      .then((response) => {
        const msg = `Create response data: ${response.data}` 
        document.querySelector("#call-result").innerHTML = msg
      })
  }
}

const getImportableProjects = async () => {
  /* Retrieve projects from Shotgrid

    Via the custom `get-importable-projects` endpoint, receive an array
    of projects that can be imported from Shotgrid, i.e. have a valid `name` and
    `code`.
  */
  const headers = {"Authorization": `Bearer ${accessToken}`};

  const response = await axios.get(
    `/api/addons/${addonName}/${addonVersion}/get-importable-projects`,
    {headers}
  );
  return response.data
}

const getShotgridProjects = () => {
  /* Retrieve projects from Shotgrid and populate the Import dropdown.

    Relies in `getImportableProjects` to get the projects, then we ensure the
    fetched projects contain all needed information and populate the Import 
    dropdown.
  */
  getImportableProjects()
  .then((shotgridProjects) => {
    const foundProjects = []
    if (shotgridProjects) {
      shotgridProjects.forEach((el) => {
        if (el.projectName && el.projectCode && el.ayonId == null) {
          let projectOption = document.createElement("option")
          projectOption.innerHTML = `${el.projectName} (${el.projectCode}) - Shotgrid ID: ${el.shotgridId}`
          projectOption.setAttribute("value", `${el.projectName}`)
          projectOption.setAttribute("data-project-name", `${el.projectName}`)
          projectOption.setAttribute("data-project-code", `${el.projectCode}`)
          foundProjects.push(projectOption)
        }
      })
    }
    if (foundProjects) {
      populateImportDropdown(foundProjects);
    }
    return foundProjects
  });
}


const populateImportDropdown = (projectsArray) => {
  /* Given a non-empty array of projects, add the them to the Select Dropdwon
    Also enable the "Sync Shotgrid Project" button when choosing a valid option or
    removing it when its not.
  */
  
  let projectsImportPlaceholderOption = document.getElementById("fetching-shotgrid-option")

  if (projectsArray) {
    projectsImportPlaceholderOption.innerHTML = "Choose a Project to Import and Sync..."
    let projectsImportSelect = document.getElementById("new-shotgrid-projects-select")
    let projectsImportButton= document.getElementById("sg-import-shotgrid-project")

    projectsArray.forEach((projectOption) => {
      projectsImportSelect.appendChild(projectOption)
    });

    projectsImportSelect.addEventListener('change', () => {
        let syncProjectButton = document.getElementById("sg-sync-from-shotgrid")

        if (projectsImportSelect.selectedOptions[0].value) {
          projectsImportButton.disabled = false
          projectsImportButton.addEventListener("click", importProjectCallback);

        } else {
          projectsImportButton.disabled = true
          projectsImportButton.removeEventListener("click", importProjectCallback);
        }
    });
  } else {
    projectsImportPlaceholderOption.innerHTML = "Unable to find valid Projects."
  };
}

const importProjectCallback = () => {
  /* Trigger the Addon API endpoint to Sync a project.
    Named function so we can remove it from the event handler.
  */
  let projectsImportSelect = document.getElementById("new-shotgrid-projects-select")
  let projectName = projectsImportSelect.selectedOptions[0].getAttribute("data-project-name");
  let projectCode = projectsImportSelect.selectedOptions[0].getAttribute("data-project-code");

  if (projectName) {
    importProject(projectName, projectCode);
  }
}


const getSyncableProjects = () => {
  /* Query Ayon for all existing projects that have the shotgridID field not null
    and append them to the Sync projects dropdown. 
  */
  axios({
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
  }).then((result) => {
    const foundProjects = []
    if (result.data) {
      if (result.data.data.projects.edges) {
        result.data.data.projects.edges.forEach((el) => {
          if (el.node.attrib.shotgridId) {
            let projectOption = document.createElement("option")
            projectOption.innerHTML = `${el.node.name} (${el.node.code}) - Shotgrid ID: ${el.node.attrib.shotgridId}`
            projectOption.setAttribute("value", `${el.node.name}`)
            foundProjects.push(projectOption)
          }
        })
      }
    }
    if (foundProjects) {
      populateSyncDropdown(foundProjects);
    }
    return foundProjects
  });
}

const populateSyncDropdown = (projectsArray) => {
  /* Given a non-empty array of projects, add the them to the Select Dropdwon
    Also enable the "Sync Shotgrid Project" button when choosing a valid option or
    removing it when its not.
  */
  if (projectsArray) {
    let projectsSyncSelect = document.getElementById("manage-shotgrid-projects-select");

    projectsArray.forEach((projectOption) => {
      projectsSyncSelect.appendChild(projectOption)
    });

    projectsSyncSelect.addEventListener('change', () => {
        let syncProjectButton = document.getElementById("sg-sync-from-shotgrid")

        if (projectsSyncSelect.selectedOptions[0].value) {
          syncProjectButton.disabled = false
          syncProjectButton.addEventListener("click", syncProjectCallback);

        } else {
          syncProjectButton.disabled = true
          syncProjectButton.removeEventListener("click", syncProjectCallback);
        }
    });
    
  };
}

const syncProjectCallback = () => {
  /* Trigger the Addon API endpoint to Sync a project.
    Named function so we can remove it from the event handler.
  */
  let projectsSyncSelect = document.getElementById("manage-shotgrid-projects-select");
  let projectName = projectsSyncSelect.selectedOptions[0].value

  if (projectName) {
    syncProject(`${projectName}`);
  }
}

document.addEventListener('DOMContentLoaded', () => {
 init()
})
