library(shiny)
source("config.R")
source("R/data_and_models.R")
source("R/strategy.R")
data.table::setDTthreads(1L) # These small tables are faster without thread startup.

bundle_path <- "models/prototype.rds"
if(!file.exists(bundle_path)) stop("Run Rscript scripts/run_analysis.R first. See README.md for data placement.")
bundle <- readRDS(bundle_path)
if(is.null(bundle$metadata$code_md5) ||
   !identical(bundle$metadata$code_md5,tools::md5sum(names(bundle$metadata$code_md5))))
  stop("Model bundle does not match the calculation source. Rerun scripts/run_analysis.R.")
if(!length(bundle$scenarios)) stop("No supported real scenarios were built. See outputs/factual_exclusions.csv.")
model <- bundle$model
ui <- fluidPage(
  titlePanel("Pit this lap or stay out?"),
  p("Provisional dry/green local-cycle testing. Positive gap means focal driver behind. Future stops and sets are assumptions. Probabilities require further calibration."),
  selectInput("scenario","Scenario",choices=names(bundle$scenarios)),
  fluidRow(
    column(3,numericInput("gap","Focal minus rival gap (seconds)",1,step=.1)),
    column(3,numericInput("age","Focal tyre age at completed boundary",12,min=0,step=1)),
    column(3,selectInput("compound","Proposed focal replacement",choices=NULL)),
    column(3,numericInput("rival_stop","Assumed rival pit lap",20,min=1,step=1))
  ),
  fluidRow(
    column(3,numericInput("teammate_stop","Assumed teammate pit lap",20,min=1,step=1)),
    column(3,numericInput("prior_age","Proposed replacement prior use (laps)",0,min=0,step=1))
  ),
  actionButton("compare","Compare"),
  verbatimTextOutput("assumptions"),
  textOutput("recommendation"),
  div(style="overflow-x:auto",tableOutput("results")),
  plotOutput("gap_plot",height="280px"),
  p("Expected team points: unavailable. Requires a credible surrounding-field projection to the finish, later stops and applicable race points rules.")
)
server <- function(input,output,session) {
  observeEvent(input$scenario, {
    s <- bundle$scenarios[[input$scenario]]
    updateNumericInput(session,"gap",value=s$gap_sec)
    updateNumericInput(session,"age",value=s$states$focal$tyre_age,max=s$states$focal$age_max-4)
    updateSelectInput(session,"compound",choices=s$states$focal$feasible_compounds,
                      selected=s$states$focal$new_compound)
    updateNumericInput(session,"rival_stop",value=s$rival_stop,
      min=s$current_lap,max=s$current_lap+3)
    updateNumericInput(session,"teammate_stop",value=s$teammate_stop,
      min=s$current_lap,max=s$current_lap+2)
    updateNumericInput(session,"prior_age",value=0)
  })
  comparison <- eventReactive(input$compare, {
    s <- bundle$scenarios[[input$scenario]]
    s$gap_sec <- input$gap; s$states$focal$tyre_age <- input$age
    s$states$focal$new_compound <- input$compound
    s$states$focal$new_set_prior_age <- input$prior_age
    s$rival_stop <- input$rival_stop; s$teammate_stop <- input$teammate_stop
    tryCatch(compare_strategies(s,model),error=function(e)
      validate(need(FALSE,conditionMessage(e))))
  },ignoreInit=TRUE)
  output$assumptions <- renderText({
    s<-bundle$scenarios[[input$scenario]]
    paste("Current decision lap:",s$current_lap," Shared completed boundary:",s$boundary,
      "\nCutoff (session seconds):",round(s$cutoff_sec,3),
      "\nRival proposed compound:",s$states$rival$new_compound,
      "\nUsable replacement inventory is assumed; actual set inventory is unavailable.",
      "\nOther cars: constant recent pace, no stops; rejoin proximity delay",s$traffic_loss_sec,"seconds.",
      "\nTeammate:",if("teammate" %in% names(s$states)) s$states$teammate$driver else "unavailable at cutoff",
      "\nBox waiting uses approximate crossing-clock arrival and assumed",s$box_service_sec,"second service.",
      "\nResults remain from the last Compare click.")
  })
  output$recommendation <- renderText(comparison()$recommendation)
  # Exactly the calculation function's result table; Shiny defines no metrics.
  output$results <- renderTable(comparison()$table,digits=3,na="Unavailable")
  output$gap_plot <- renderPlot({
    z<-comparison()$ledger[role=="focal"]
    strategies<-unique(z$strategy); cols<-seq_along(strategies)
    plot(range(z$lap),range(c(z$gap_sec,0)),type="n",xlab="Common completed lap",
      ylab="Focal minus rival arrival (seconds)")
    abline(h=0,lty=2)
    for(i in seq_along(strategies)) {
      a<-z[strategy==strategies[i]]; lines(a$lap,a$gap_sec,col=cols[i],type="b")
    }
    legend("topright",strategies,col=cols,lty=1,bty="n")
  })
}
shinyApp(ui,server)
