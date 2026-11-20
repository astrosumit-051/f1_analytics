library(shiny)
source("data.R",local=TRUE)
root <- normalizePath(Sys.getenv("F1_PROJECT_ROOT",".."),mustWork=FALSE)
data <- tryCatch(load_handoffs(root),error=function(e) list(error=conditionMessage(e)))
pct <- function(x) if(is.finite(x)) sprintf("%.1f%%",100*x) else "Unavailable"

make_ui <- function(data) {
  if(!is.null(data$error)) return(fluidPage(titlePanel("F1 undercut window"),
    h3("Handoff unavailable"),p(data$error),p("See demo/README.md for data placement or explicit synthetic mode.")))
  models<-unique(data$window$model_id)
  fluidPage(tags$head(tags$style(HTML("
    body{background:#f5f7fa;color:#183047;font-family:Arial,sans-serif}
    .container-fluid{max-width:1280px;margin:auto;padding:22px 30px}
    h1{font-weight:700;font-size:32px} h3{font-size:21px}
    .leadtext{font-size:16px;max-width:950px;line-height:1.6}
    .well{background:white;border:1px solid #dde3ea;box-shadow:none}
    .panelview{background:white;padding:18px 22px;border:1px solid #e0e5eb;border-radius:8px;margin:12px 0}
    .evidence{font-weight:bold;color:#835213;padding:8px 0}
    .probability{font-size:36px;font-weight:700;color:#185a80}
    .note{color:#526574;font-size:13px;line-height:1.5}
    .nav-tabs{margin-top:20px}.shiny-output-error-validation{color:#80511e}
    table{font-size:13px} .btn{border-radius:5px}
  "))),
  titlePanel("F1 undercut window"),
  p(class="leadtext","Explore the association between the starting gap, rival response and staying ahead after a pit cycle. Strategies were chosen by teams; these comparisons do not prove one action is better."),
  div(class="evidence",data$evidence),
  p(class="note","Development view. Training observations only. Production model validation is pending; protected seasons are not displayed."),
  sidebarLayout(sidebarPanel(width=3,
    selectInput("outcome","Evaluation boundary",c("Common lap | compare responses"="success_common_h3","Pair-specific | primary outcome"="success_h3")),
    selectInput("delay","Observed rival delay",c("One lap"="d1","Two or three laps"="d23")),
    selectInput("model","Supplied model",if(length(models)) models else "Model pending"),
    sliderInput("gap","Starting gap (seconds)",min=.1,max=6,value=2,step=.1),
    checkboxInput("compare_delays","Overlay both response groups",TRUE),
    p(class="note","The curve is conditional on the rival stopping within three laps. Other model features are held at the supplied training profile. No user input changes the model or outcome definition."),
    downloadButton("download","Download displayed grid"),
    if(Sys.getenv("F1_LOCAL_LAUNCH")=="1") actionButton("stop_local","Stop local app")),
  mainPanel(width=9,
    div(class="panelview",h3("Model probability"),div(class="probability",textOutput("probability")),
      textOutput("uncertainty"),p(class="note",textOutput("calculation_status"))),
    tabsetPanel(
      tabPanel("Window",div(class="panelview",plotOutput("window",height="380px"),
        p(class="note",textOutput("boundary_note")),h3("50% and 25% crossings"),tableOutput("crossings"),
        p(class="note","Crossings are interpolated only inside supported gaps. An absent or ambiguous crossing remains unavailable. A shaded band is a supplied pointwise race-bootstrap interval, not a prediction interval."),
        h3("Observed gap bands"),tableOutput("gap_rates"))),
      tabPanel("Response comparisons",div(class="panelview",h3("Sustained chaser success at the common lap"),tableOutput("comparison"),
        h3("Defender at the common lap"),tableOutput("defender"),
        p(class="note","The defender column shows one minus immediate common-lap chaser success. It does not claim sustained defence. Missing follow-up is retained as missing; chosen response delays are not randomized."),
        h3("No response within three laps"),textOutput("no_response"))),
      tabPanel("Recorded examples",div(class="panelview",h3("Observed success and failure"),tableOutput("examples"),
        p(class="note","Examples use the nearest complete starting gaps in the selected training group. They are observations, not counterfactual predictions. Synthetic mode labels every example synthetic."))),
      tabPanel("Definitions and sources",div(class="panelview",
        p("Gap is chaser minus leader at the end of ref_lap; positive means behind. Rival delay is leader stop lap minus chaser stop lap."),
        p("Primary success: ahead at comparison_lap and each of the next three boundaries. Common-lap success: ahead at chaser_stop_lap + 4 and each of the next three boundaries."),
        p("Outcomes interrupted by stops, neutralisation, rain, retirement or timing problems are missing, never failures. Cars between the drivers are retained."),
        p("SC/VSC and defender technical workflows are documented under analysis/extensions. 2026 transfer and the locked 2025 test are unavailable until shared authorization."),
        tableOutput("sources")))))))
}

make_server <- function(data) function(input,output,session) {
  if(Sys.getenv("F1_LOCAL_LAUNCH")=="1") observeEvent(input$stop_local, { stopApp() },ignoreInit=TRUE)
  if(!is.null(data$error)) return(invisible(NULL))
  snapshot <- reactive({req(input$model,input$outcome,input$delay,input$gap)
    scenario_snapshot(data,input$model,input$outcome,input$delay,input$gap)})
  output$probability <- renderText(pct(snapshot()$value$probability))
  output$uncertainty <- renderText({v<-snapshot()$value
    if(is.finite(v$lo)&&is.finite(v$hi)) paste("Supplied 95% pointwise interval:",pct(v$lo),"to",pct(v$hi)) else "95% model interval unavailable in the supplied grid."})
  output$calculation_status <- renderText(if(grepl("unavailable",data$grid_status)) data$grid_status else snapshot()$value$status)
  output$boundary_note <- renderText(if(input$outcome=="success_common_h3")
    "Common-lap outcomes compare response groups at the same defined boundary. Points show observed rates in one-second gap bands."
    else "Pair-specific primary outcome. Only the selected delay is plotted; cross-delay comparisons use the common-lap view.")
  output$window <- renderPlot({s<-snapshot();w<-s$window
    validate(need(nrow(w)>=2,"Model curve pending or outside observed training support. Observed counts remain available below."))
    plot(w$gap_sec,w$p_success,type="n",ylim=c(0,1),xlim=c(0,6),xlab="Starting gap (s)",ylab="Probability of sustained chaser success")
    abline(h=c(.25,.5),lty=3,col="gray65");abline(v=input$gap,lty=2,col="#526574")
    groups<-if(isTRUE(input$compare_delays)&&input$outcome=="success_common_h3") c("d1","d23") else input$delay
    colors<-c(d1="#185a80",d23="#a34c27")
    for(g in groups) {
      z<-supported_window(data,input$model,input$outcome,g)
      if(nrow(z)<2) next
      if(all(is.finite(z$p_lo)&is.finite(z$p_hi))) polygon(c(z$gap_sec,rev(z$gap_sec)),c(z$p_lo,rev(z$p_hi)),col=adjustcolor(colors[g],alpha.f=.15),border=NA)
      lines(z$gap_sec,z$p_success,col=colors[g],lwd=2)
    }
    r<-s$rates
    if(nrow(r)) points(r$mean_gap,r$observed,pch=19,col=colors[input$delay])
    legend("topright",paste(groups,"model curve"),col=colors[groups],lwd=2,bty="n")
  })
  output$crossings<-renderTable(snapshot()$crossings,digits=3,na="Unavailable")
  output$gap_rates<-renderTable({r<-snapshot()$rates;validate(need(nrow(r)>0,"No observed cases for this group."));r},digits=3,na="Unavailable")
  output$comparison<-renderTable({r<-snapshot()$comparison
    labels<-c(d1="Rival waited 1 lap",d23="Rival waited 2-3 laps",same_lap="Same-lap stops",leader_first="Rival stopped first")
    if(nrow(r)) r$delay_group<-unname(labels[r$delay_group]);r
  },digits=3,na="Unavailable")
  output$defender<-renderTable({r<-snapshot()$defender;r$chaser_not_ahead<-1-r$observed;r$observed<-NULL
    names(r)[names(r)=="successes"]<-"chaser_ahead_count";r
  },digits=3,na="Unavailable")
  output$no_response<-renderText(no_response_summary(data$nr))
  output$examples<-renderTable({r<-snapshot()$cases;r<-r[!is.na(r[[input$outcome]]),,drop=FALSE]
    r<-r[order(abs(r$gap_before_sec-input$gap),r$battle_id),,drop=FALSE];r<-r[!duplicated(r[[input$outcome]]),,drop=FALSE]
    validate(need(nrow(r)>0,"No complete recorded examples for this group/outcome."))
    data.frame(evidence=if(data$mode=="fake") "SYNTHETIC" else "Training observation",race=r$event_id,
      chaser=r$chaser,rival=r$leader,gap_sec=r$gap_before_sec,common_lap=r$common_lap,
      comparison_lap=r$comparison_lap,sustained_success=ifelse(r[[input$outcome]]==1,"Yes","No"))
  },digits=3,na="Unavailable")
  output$sources<-renderTable(data.frame(path=names(data$source_md5),md5=unname(data$source_md5)))
  output$download<-downloadHandler(filename=function() "displayed_window.csv",content=function(file) {
    w<-snapshot()$window;w$evidence<-rep(data$evidence,nrow(w));write.csv(w,file,row.names=FALSE,na="NA")
  })
}
ui<-make_ui(data);server<-make_server(data)
shinyApp(ui,server)
