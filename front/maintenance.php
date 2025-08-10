<?php
  require 'php/templates/header.php';
  require 'php/templates/modals.php';
?>

<!-- Page ------------------------------------------------------------------ -->
<div class="content-wrapper" id="maintenancePage">

<!-- Main content ---------------------------------------------------------- -->
<section class="content">
  
<script>
  showSpinner();
</script>

<?php

// Size and last mod of DB ------------------------------------------------------

$nax_db = str_replace('front', 'db', getcwd()).'/app.db';
$nax_wal = str_replace('front', 'db', getcwd()).'/app.db-wal';
$nax_db_size = number_format((filesize($nax_db) / 1000000),2,",",".") . ' MB';
$nax_wal_size = number_format((filesize($nax_wal) / 1000000),2,",",".") . ' MB';
$nax_db_mod = date ("F d Y H:i:s", filemtime($nax_db));


// Table sizes -----------------------------------------------------------------

$tableSizesHTML = "";
                        
// Open a connection to the SQLite database
$db = new SQLite3($nax_db);

// Retrieve the table names from sqlite_master
$query = "SELECT name FROM sqlite_master WHERE type='table'";
$result = $db->query($query);

// Iterate over the tables and get the row counts
while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $tableName = $row['name'];
    $query = "SELECT COUNT(*) FROM $tableName";
    $countResult = $db->querySingle($query);
    $tableSizesHTML = $tableSizesHTML . "$tableName (<b>$countResult</b>), ";
}

// Close the database connection
$db->close();
                            

?>

      <div class="row">
          <div class="col-md-12">
          <div class="box" id="Maintain-Status">
              <div class="box-header with-border">
                <h3 class="box-title">
                  <i class="fa fa-display"></i>         
                  <?= lang('Maintenance_Status');?>
                </h3>
              </div>
              <div class="box-body" style="padding-bottom: 5px;">
                <div class="db_info_table">
                    <div class="db_info_table_row">                      
                        <div class="db_info_table_cell" style="min-width: 140px"><?= lang('Maintenance_version');?>
                          <a href="https://github.com/jokob-sk/NetAlertX/blob/main/docs/VERSIONS.md" target="_blank"> <span><i class="fa fa-circle-question"></i></a></span>
                        </div>
                        <div class="db_info_table_cell">
                        <div class="version" id="version" data-build-time="<?php echo file_get_contents( "buildtimestamp.txt");?>">
                          <?php echo '<span id="new-version-text" class="myhidden"><i class="fa-solid fa-rocket fa-beat"></i> ' .lang('Maintenance_new_version').'</span>'.'<span id="current-version-text" class="myhidden">' .lang('Maintenance_current_version').'</span>';?>
                        </div>
                        </div>
                    </div>
                    <div class="db_info_table_row">
                        <div class="db_info_table_cell" style="min-width: 140px"><?= lang('Maintenance_built_on');?></div>
                        <div class="db_info_table_cell">                               
                            <?php echo date("Y-m-d", ((int)file_get_contents( "buildtimestamp.txt")));?> 
                        </div>
                    </div>
                    <div class="db_info_table_row">
                        <div class="db_info_table_cell" style="min-width: 140px"><?= lang('Maintenance_Running_Version');?></div>
                        <div class="db_info_table_cell">                               
                          <?php include 'php/templates/version.php'; ?> 
                        </div>
                    </div>
                    <div class="db_info_table_row">
                        <div class="db_info_table_cell" style="min-width: 140px"><?= lang('Maintenance_database_path');?></div>
                        <div class="db_info_table_cell">
                            <?php echo $nax_db;?> 
                        </div>
                    </div>
                    <div class="db_info_table_row">
                        <div class="db_info_table_cell"><?= lang('Maintenance_database_size');?></div>
                        <div class="db_info_table_cell">
                            <?php echo $nax_db_size;?> (wal: <?php echo $nax_wal_size;?>)
                        </div>                        
                    </div>
                    <div class="db_info_table_row">
                        <div class="db_info_table_cell"><?= lang('Maintenance_database_rows');?></div>
                        <div class="db_info_table_cell">
                            <?php echo $tableSizesHTML;?>
                        </div>                        
                    </div>
                    <div class="db_info_table_row">
                        <div class="db_info_table_cell"><?= lang('Maintenance_database_lastmod');?></div>
                        <div class="db_info_table_cell">
                            <?php echo $nax_db_mod;?>
                        </div>
                    </div>           
                </div>                
              </div>
              <!-- /.box-body -->
            </div>
          </div>
      </div>

    <div class="nav-tabs-custom">
      <ul class="nav nav-tabs">
        <li class="active">
          <a id="tab_DBTools_id" href="#tab_DBTools" data-toggle="tab">
            <i class="fa fa-toolbox"></i> 
            <?= lang('Maintenance_Tools_Tab_Tools');?>
          </a>
        </li>
        <li>
          <a id="tab_BackupRestore_id" href="#tab_BackupRestore" data-toggle="tab">
            <i class="fa fa-file-shield"></i> 
            <?= lang('Maintenance_Tools_Tab_BackupRestore');?>
          </a>
        </li>
        <li>
          <a id="tab_Logging_id" href="#tab_Logging" data-toggle="tab">
            <i class="fa fa-triangle-exclamation"></i> 
            <?= lang('Maintenance_Tools_Tab_Logging');?>
          </a>
        </li>
        <li>
          <a id="tab_multiEdit_id" href="#tab_multiEdit" data-toggle="tab">
            <i class="fa fa-pencil pointer" ></i>  
            <?= lang('Device_MultiEdit');?>
          </a>
        </li>
        <li>
          <a id="tab_initCheck_id" href="#tab_initCheck" data-toggle="tab">
            <i class="fa-solid fa-check"></i> 
            <?= lang('Maintenance_InitCheck');?>
          </a>
        </li>
      </ul>
    <div class="tab-content spinnerTarget">
        <div class="tab-pane active" id="tab_DBTools">
                <div class="db_info_table">
                    <div class="db_info_table_row">
                        <div class="db_tools_table_cell_a" >
                            <button type="button" class="btn btn-default pa-btn pa-btn-delete bg-red dbtools-button" id="btnDeleteMAC" onclick="askDeleteDevicesWithEmptyMACs()"><?= lang('Maintenance_Tool_del_empty_macs');?></button>
                        </div>
                        <div class="db_tools_table_cell_b"><?= lang('Maintenance_Tool_del_empty_macs_text');?></div>
                    </div>
                    <div class="db_info_table_row">
                        <div class="db_tools_table_cell_a" >
                            <button type="button" class="btn btn-default pa-btn pa-btn-delete bg-red dbtools-button" id="btnDeleteMAC" onclick="askDeleteAllDevices()"><?= lang('Maintenance_Tool_del_alldev');?></button>
                        </div>
                        <div class="db_tools_table_cell_b"><?= lang('Maintenance_Tool_del_alldev_text');?></div>
                    </div>
                    <div class="db_info_table_row">
                        <div class="db_tools_table_cell_a" >
                            <button type="button" class="btn btn-default pa-btn pa-btn-delete bg-red dbtools-button" id="btnDeleteUnknown" onclick="askDeleteUnknown()"><?= lang('Maintenance_Tool_del_unknowndev');?></button>
                        </div>
                        <div class="db_tools_table_cell_b"><?= lang('Maintenance_Tool_del_unknowndev_text');?></div>
                    </div>
                    <div class="db_info_table_row">
                        <div class="db_tools_table_cell_a" >
                            <button type="button" class="btn btn-default pa-btn pa-btn-delete bg-red dbtools-button" id="btnDeleteEvents" onclick="askDeleteEvents()"><?= lang('Maintenance_Tool_del_allevents');?></button>
                        </div>
                        <div class="db_tools_table_cell_b"><?= lang('Maintenance_Tool_del_allevents_text');?></div>
                    </div>
                    <div class="db_info_table_row">
                        <div class="db_tools_table_cell_a" >
                            <button type="button" class="btn btn-default pa-btn pa-btn-delete bg-red dbtools-button" id="btnDeleteEvents30" onclick="askDeleteEvents30()"><?= lang('Maintenance_Tool_del_allevents30');?></button>
                        </div>
                        <div class="db_tools_table_cell_b"><?= lang('Maintenance_Tool_del_allevents30_text');?></div>
                    </div>
                    <div class="db_info_table_row">
                        <div class="db_tools_table_cell_a" >
                            <button type="button" class="btn btn-default pa-btn pa-btn-delete bg-red dbtools-button" id="btnDeleteActHistory" onclick="askDeleteActHistory()"><?= lang('Maintenance_Tool_del_ActHistory');?></button>
                        </div>
                        <div class="db_tools_table_cell_b"><?= lang('Maintenance_Tool_del_ActHistory_text');?></div>
                    </div>
                    <div class="db_info_table_row">
                        <div class="db_tools_table_cell_a" >
                            <button type="button" class="btn btn-default pa-btn pa-btn-delete bg-red dbtools-button" id="btnRestartServer" onclick="askRestartBackend()"><?= lang('Maint_RestartServer');?></button>
                        </div>
                        <div class="db_tools_table_cell_b"><?= lang('Maint_Restart_Server_noti_text');?></div>
                    </div>
                </div>
        </div>

        <!-- ---------------------------Backup restore -------------------------------------------- -->
        <div class="tab-pane" id="tab_BackupRestore">
          <div class="db_info_table">
            <div class="db_info_table_row">
              <div class="db_tools_table_cell_a" >
                  <button type="button" class="btn btn-default pa-btn bg-green dbtools-button" id="btnExportCSV" onclick="ExportCSV()"><?= lang('Maintenance_Tool_ExportCSV');?></button>
              </div>
              <div class="db_tools_table_cell_b"><?= lang('Maintenance_Tool_ExportCSV_text');?></div>
            </div>
            <div class="db_info_table_row">
                <div class="db_tools_table_cell_a" >
                    <button type="button" class="btn btn-default pa-btn pa-btn-delete bg-red dbtools-button" id="btnImportCSV" onclick="askImportCSV()"><?= lang('Maintenance_Tool_ImportCSV');?></button>
                </div>
                <div class="db_tools_table_cell_b"><?= lang('Maintenance_Tool_ImportCSV_text');?></div>
            </div>
            <div class="db_info_table_row">
                <div class="db_tools_table_cell_a" >
                    <button type="button" class="btn btn-default pa-btn pa-btn-delete bg-red dbtools-button" id="btnImportPastedCSV" onclick="askImportPastedCSV()"><?= lang('Maintenance_Tool_ImportPastedCSV');?></button>
                </div>
                <div class="db_tools_table_cell_b"><?= lang('Maintenance_Tool_ImportPastedCSV_text');?></div>
            </div>  
            <div class="db_info_table_row">
              <div class="db_tools_table_cell_a" >
                  <button type="button" class="btn btn-default pa-btn bg-green dbtools-button" id="btnDownloadConfig" onclick="DownloadConfig()"><?= lang('Maintenance_Tool_DownloadConfig');?></button>
              </div>
              <div class="db_tools_table_cell_b"><?= lang('Maintenance_Tool_DownloadConfig_text');?></div>
            </div>   
            <div class="db_info_table_row">
                <div class="db_tools_table_cell_a" >
                    <button type="button" class="btn btn-default pa-btn pa-btn-delete bg-red dbtools-button" id="btnImportPastedConfig" onclick="askImportPastedConfig()"><?= lang('Maintenance_Tool_ImportPastedConfig');?></button>
                </div>
                <div class="db_tools_table_cell_b"><?= lang('Maintenance_Tool_ImportPastedConfig_text');?></div>
            </div>
            <div class="db_info_table_row">
              <div class="db_tools_table_cell_a" >
                  <button type="button" class="btn btn-default pa-btn bg-green dbtools-button" id="btnDownloadWorkflows" onclick="DownloadWorkflows()"><?= lang('Maintenance_Tool_DownloadWorkflows');?></button>
              </div>
              <div class="db_tools_table_cell_b"><?= lang('Maintenance_Tool_DownloadWorkflows_text');?></div>
            </div>                    
          </div>
        </div>
        <!-- ---------------------------Logging-------------------------------------------- -->
        <div class="tab-pane" id="tab_Logging">
          <div class="container">
            <div class="row actions">
              <div class="col-sm-2">
                <div class="form-check toggle">
                  <label class="form-check-label pointer" for="logsAutoRefresh">
                    <input class="form-check-input" type="checkbox" id="logsAutoRefresh" onchange="toggleAutoRefresh()" />
                    Auto-refresh
                  </label>
                </div>
              </div>
              <div class="col-sm-2">
                <div class="form-check  toggle">
                  <label class="form-check-label pointer" for="logsAutoScroll">
                    <input class="form-check-input" type="checkbox" checked id="logsAutoScroll" />
                    Auto-scroll
                  </label>
                </div>
              </div>
              <div class="col-sm-8">
                <div class="form-inline toggle">                  
                  <input class="form-control" type="text" id="logsFilter" oninput="applyFilter()" placeholder="Filter lines with text..." />
                </div>
              </div>
            </div>
          </div>
          <div class="db_info_table">            
            <div id="logsPlc"></div>                                
          </div>
        </div>
        
        <!-- ---------------------------Bulk edit -------------------------------------------- -->
        <div class="tab-pane" id="tab_multiEdit">
            <div class="db_info_table">
                <div class="box box-solid">
                    <?php
                      require 'multiEditCore.php';
                    ?>

                </div>
            </div>
        </div>

        <!-- ---------------------------Init check -------------------------------------------- -->
        <div class="tab-pane" id="tab_initCheck">
            <div class="db_info_table">
                <div class="box box-solid">
                  
                    <?php
                      require 'initCheck.php';
                    ?>

                </div>
            </div>
        </div>      

        
        <!-- ------------------------------------------------------------------------------ -->

      </div>
      </div>

      <div class="box-body " style="text-align: center;">
        <h5 class="text-aqua" style="font-size: 16px;">
          <span id="lastCommit">
            
          </span>
          <span id="lastDockerUpdate">
            
          </span>          
        </h5>
      </div>
      
      
    </div>



  </section>

  

  <!-- /.content -->
  <?php
    require 'php/templates/footer.php';
  ?>
</div>
<!-- /.content-wrapper -->

<!-- ----------------------------------------------------------------------- -->



<script>

var emptyArr = ['undefined', "", undefined, null];
var selectedTab                 = 'tab_DBTools_id';

initializeTabs();

// -----------------------------------------------------------
// delete devices with emty macs
function askDeleteDevicesWithEmptyMACs () {
  // Ask 
  showModalWarning('<?= lang('Maintenance_Tool_del_empty_macs_noti');?>', '<?= lang('Maintenance_Tool_del_empty_macs_noti_text');?>',
    'Cancel', 'Delete', 'deleteDevicesWithEmptyMACs');
}
// -----------------------------------------------------------
function deleteDevicesWithEmptyMACs()
{ 
  // Delete device
  $.get('php/server/devices.php?action=deleteAllWithEmptyMACs', function(msg) {
    showMessage (msg);
    write_notification(`[Maintenance] All devices witout a Mac manually deleted`, 'info')
  });
}

// -----------------------------------------------------------
// delete all devices 
function askDeleteAllDevices () {
  // Ask 
  showModalWarning('<?= lang('Maintenance_Tool_del_alldev_noti');?>', '<?= lang('Maintenance_Tool_del_alldev_noti_text');?>',
    '<?= lang('Gen_Cancel');?>', '<?= lang('Gen_Delete');?>', 'deleteAllDevices');
}
// -----------------------------------------------------------
function deleteAllDevices()
{ 
  // Delete device
  $.get('php/server/devices.php?action=deleteAllDevices', function(msg) {
    showMessage (msg);
    write_notification(`[Maintenance] All devices manually deleted`, 'info')
  });
}

// -----------------------------------------------------------
// delete all (unknown) devices 
function askDeleteUnknown () {
  // Ask 
  showModalWarning('<?= lang('Maintenance_Tool_del_unknowndev_noti');?>', '<?= lang('Maintenance_Tool_del_unknowndev_noti_text');?>',
    '<?= lang('Gen_Cancel');?>', '<?= lang('Gen_Delete');?>', 'deleteUnknownDevices');
}
// -----------------------------------------------------------
function deleteUnknownDevices()
{ 
  // Execute
  $.get('php/server/devices.php?action=deleteUnknownDevices', function(msg) {
    showMessage (msg);
    write_notification(`[Maintenance] Unknown devices manually deleted`, 'info')
  });
}

// -----------------------------------------------------------
// delete all Events 
function askDeleteEvents () {
  // Ask 
  showModalWarning('<?= lang('Maintenance_Tool_del_allevents_noti');?>', '<?= lang('Maintenance_Tool_del_allevents_noti_text');?>',
    '<?= lang('Gen_Cancel');?>', '<?= lang('Gen_Delete');?>', 'deleteEvents');
}
// -----------------------------------------------------------
function deleteEvents()
{ 
  // Execute
  $.get('php/server/devices.php?action=deleteEvents', function(msg) {
    showMessage (msg);
    write_notification(`[Maintenance] Events manually deleted (all)`, 'info')
  });
}

// -----------------------------------------------------------
// delete all Events older than 30 days
function askDeleteEvents30 () {
  // Ask 
  showModalWarning('<?= lang('Maintenance_Tool_del_allevents30_noti');?>', '<?= lang('Maintenance_Tool_del_allevents30_noti_text');?>',
    '<?= lang('Gen_Cancel');?>', '<?= lang('Gen_Delete');?>', 'deleteEvents30');
}
// -----------------------------------------------------------
function deleteEvents30()
{ 
  // Execute
  $.get('php/server/devices.php?action=deleteEvents30', function(msg) {
    showMessage (msg);
    write_notification(`[Maintenance] Events manually deleted (last 30 days kep)`, 'info')
  });
}

// -----------------------------------------------------------
// delete History 
function askDeleteActHistory () {
  // Ask 
  showModalWarning('<?= lang('Maintenance_Tool_del_ActHistory_noti');?>', '<?= lang('Maintenance_Tool_del_ActHistory_noti_text');?>',
    '<?= lang('Gen_Cancel');?>', '<?= lang('Gen_Delete');?>', 'deleteActHistory');
}
function deleteActHistory()
{ 
  // Execute
  $.get('php/server/devices.php?action=deleteActHistory', function(msg) {
    showMessage (msg);
  });
}

// -----------------------------------------------------------
// Import pasted Config ASK
function askImportPastedConfig() {

  // Add new icon as base64 string 
  showModalInput ('<i class="fa fa-square-plus pointer"></i> <?= lang('Maintenance_Tool_ImportConfig_noti');?>', '<?= lang('Maintenance_Tool_ImportPastedConfig_noti_text');?>',
    '<?= lang('Gen_Cancel');?>', '<?= lang('Gen_Okay');?>', 'UploadConfig');
}

// -----------------------------------------------------------
// Upload Settings Config
function UploadConfig()
{ 
  appConf = $('#modal-input-textarea').val()
  // encode for import
  appConfBase64 = btoa(appConf)

  // import
  $.post('php/server/query_replace_config.php', { base64data: appConfBase64, fileName: "app.conf" }, function(msg) {
    console.log(msg);            
    // showMessage(msg);            
    write_notification(`[Maintenance]: ${msg}`, 'interrupt');
  });

}

// -----------------------------------------------------------
// Download Settings Config
function DownloadConfig()
{ 
  // Execute
  openInNewTab("php/server/query_config.php?file=app.conf&download=true")
}

// -----------------------------------------------------------
// Download Workflows

function DownloadWorkflows()
{ 
  // Execute
  openInNewTab("php/server/query_config.php?file=workflows.json&download=true")
}



// -----------------------------------------------------------
// Export CSV
function ExportCSV()
{ 
  // Execute
  openInNewTab("php/server/devices.php?action=ExportCSV")
}

// -----------------------------------------------------------
// Import CSV
function askImportCSV() {
  // Ask 
  showModalWarning('<?= lang('Maintenance_Tool_ImportCSV_noti');?>', '<?= lang('Maintenance_Tool_ImportCSV_noti_text');?>',
    '<?= lang('Gen_Cancel');?>', '<?= lang('Gen_Okay');?>', 'ImportCSV');
}
function ImportCSV()
{   
  // Execute
  $.get('php/server/devices.php?action=ImportCSV', function(msg) {
    showMessage (msg);
    write_notification(`[Maintenance] Devices imported from CSV file`, 'info')
  });
}

// -----------------------------------------------------------
// Import pasted CSV
function askImportPastedCSV() {

  // Add new icon as base64 string 
  showModalInput ('<i class="fa fa-square-plus pointer"></i> <?= lang('Maintenance_Tool_ImportCSV_noti');?>', '<?= lang('Maintenance_Tool_ImportPastedCSV_noti_text');?>',
    '<?= lang('Gen_Cancel');?>', '<?= lang('Gen_Okay');?>', 'ImportPastedCSV');
}

function ImportPastedCSV()
{   
  var csv = $('#modal-input-textarea').val();

  console.log(csv);

  csvBase64 = utf8ToBase64(csv);   

  console.log(csvBase64);
  

  $.post('php/server/devices.php?action=ImportCSV', { content: csvBase64 }, function(msg) {
      showMessage(msg);
      write_notification(`[Maintenance] Devices imported from pasted content`, 'info');
  });


}


// --------------------------------------------------------

// Clean log file 
var targetLogFile = "";
var logFileAction = "";


// --------------------------------------------------------

function logManage(callback) {
  targetLogFile = arguments[0];  // target
  logFileAction = arguments[1];  // action
  // Ask 
  showModalWarning('<?= lang('Gen_Purge');?>' + ' ' + arguments[1], '<?= lang('Gen_AreYouSure');?>',
    '<?= lang('Gen_Cancel');?>', '<?= lang('Gen_Okay');?>', "performLogManage");
}

// --------------------------------------------------------
function performLogManage() { 
  // Execute
  console.log("targetLogFile:" + targetLogFile)
  console.log("logFileAction:" + logFileAction)
  
  $.ajax({
    method: "POST",
    url: "php/server/util.php",
    data: { function: logFileAction, settings: targetLogFile  },
    success: function(data, textStatus) {
        showModalOk ('Result', data );
        write_notification(`[Maintenance] Log file "${targetLogFile}" manually purged`, 'info')
    }
  })
}

// --------------------------------------------------------
// scroll down the log areas
function scrollDown() {
 
    var elementToCheck = $("#tab_Logging_id");

    // Check if the parent <li> is active
    if (elementToCheck.parent().hasClass("active")) {
      var textAreas = $("#logsPlc textarea");

      textAreas.each(function() {
        $(this).scrollTop(this.scrollHeight);
      });
    }
 
}


// --------------------------------------------------------
// General initialization
// --------------------------------------------------------
function initializeTabs() {  
  setTimeout(() => {
    const key = "activeMaintenanceTab";

    // default selection
    let selectedTab = "tab_DBTools_id";

    // the #target from the URL
    let target = window.location.hash.substr(1);

    console.log(selectedTab);

    // get only the part between #...?
    if (target.includes('?')) {
      target = target.split('?')[0];
    }

    // update cookie if target specified
    if (target) {    
      selectedTab = target.endsWith("_id") ? target : `${target}_id`;
      setCache(key, selectedTab); // _id is added so it doesn't conflict with AdminLTE tab behavior
    }

    // get the tab id from the cookie (already overridden by the target)
    const cachedTab = getCache(key);
    if (cachedTab && !emptyArr.includes(cachedTab)) {
      selectedTab = cachedTab;
    }

    // Activate panel
    $('.nav-tabs a[id='+ selectedTab +']').tab('show');

    // When changed save new current tab
    $('a[data-toggle="tab"]').on('shown.bs.tab', (e) => {
      const newTabId = $(e.target).attr('id');
      setCache(key, newTabId);
    });

    // events on tab change
    $('a[data-toggle="tab"]').on('shown.bs.tab', (e) => {
      const newTarget = $(e.target).attr("href"); // activated tab
    });

    hideSpinner();
  }, 50);
}

//------------------------------------------------------------------------------
//  Logs render functionality
//------------------------------------------------------------------------------

//------------------------------------------------------------------------------
// Manages the auto-refresh functionality for the logs
let intervalId;

function toggleAutoRefresh() {
  const checkbox = $('#logsAutoRefresh')[0];

  if (checkbox.checked) {
    intervalId = setInterval(renderLogs, 1000);
  } else {
    clearInterval(intervalId);
  }
}

//------------------------------------------------------------------------------
// Manages the filter application on the logs
function applyFilter() {
      const filterText = $("#logsFilter").val().toLowerCase();
      
      $(".logs").each(function() {
        const originalText = $(this).data('originalText') || $(this).val();
        
        if (!$(this).data('originalText')) {
          $(this).data('originalText', originalText);
        }

        const filteredLines = originalText.split('\n').filter(line => 
          line.toLowerCase().includes(filterText)
        );

        $(this).val(filteredLines.join('\n'));
      });
    }

//------------------------------------------------------------------------------
// Renders all the logs
function renderLogs(customData) {
    $.ajax({
      url: 'php/components/logs.php', // PHP script URL
      type: 'POST', // Use POST method to send data
      dataType: 'html', // Expect HTML response
      // data: { items: JSON.stringify(customData) }, // Send customData as JSON
      success: function(response) {
        $('#logsPlc').html(response); // Replace container content with fetched HTML

        applyFilter();

        if($('#logsAutoScroll')[0].checked)
        {
          scrollDown(); // scroll down the logs
        }
        
      },
      error: function(xhr, status, error) {
        console.error('Error fetching infoboxes:', error);
      }
    });
  }

//------------------------------------------------------------------------------
// Init
window.onload = function asyncFooter() {
  renderLogs();

  // initializeTabs();

  try {
    $("#lastCommit").append('<a href="https://github.com/jokob-sk/NetAlertX/commits" target="_blank"><img alt="GitHub last commit" src="https://img.shields.io/github/last-commit/jokob-sk/netalertx/main?logo=github"></a>');

    $("#lastDockerUpdate").append(
      '<a href="https://github.com/jokob-sk/NetAlertX/releases" target="_blank"><img alt="Docker last pushed" src="https://img.shields.io/github/v/release/jokob-sk/NetAlertX?color=0aa8d2&logoColor=fff&logo=GitHub&label=Latest"></a>');
  } catch (error) {
    console.error('Failed to load GitHub badges:', error);
  }
};

</script>

<script>
  hideSpinner();
</script>


