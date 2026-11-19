library(shiny)

# Paths are resolved from the workspace root before Shiny switches directories.
read_input <- function(variable, fallback, required=TRUE) {
  path <- Sys.getenv(variable, fallback)
  if (!file.exists(path)) {
    if (!required) return(NULL)
    stop("Missing ", variable, " CSV: ", path, call.=FALSE)
  }
  read.csv(path, stringsAsFactors=FALSE, na.strings=c("", "NA"))
}

root <- Sys.getenv("F1_PROJECT_ROOT", "..")
pairs <- read_input("F1_PAIRS", file.path(root, "data/derived/pairs.csv"))
window <- read_input("F1_WINDOW_GRID", file.path(root, "data/derived/window_grid.csv"))
no_response <- read_input("F1_NO_RESPONSE", file.path(root, "data/derived/no_response.csv"), FALSE)
outcome <- "success_common_h3"
stopifnot(all(c("split","year","event_id","battle_id","gap_before_sec","in_core","delay_group",
                "chaser","leader","common_lap",outcome) %in% names(pairs)))
stopifnot(all(c("model_id","outcome","delay_group","gap_sec","p_success","p_lo","p_hi") %in% names(window)))

pairs <- subset(pairs, split=="train" & year %in% 2018:2023 & gap_before_sec>0 & gap_before_sec<=6)
if ("clean_window" %in% names(pairs)) pairs <- subset(pairs, clean_window==1)
if ("teammates" %in% names(pairs)) pairs <- subset(pairs, teammates==0)
stopifnot(all(pairs[[outcome]] %in% c(0L,1L,NA)))
core <- subset(pairs, in_core==1)
window <- subset(window, outcome=="success_common_h3")
fake <- any(grepl("fake_", pairs$battle_id, ignore.case=TRUE)) || any(grepl("^FAKE_", window$model_id))
draft <- any(grepl("^draft_",window$model_id))
delays <- c("One lap"="d1", "Two or three laps"="d23")
labels <- c(d1="Rival waited one lap", d23="Rival waited two or three laps",
            same_lap="Same-lap stops", leader_first="Rival stopped first")

gap_summary <- function(records) {
  bands <- cut(records$gap_before_sec, 0:6, include.lowest=TRUE)
  result <- lapply(split(records, bands, drop=TRUE), function(rows) {
    risk <- rows[[outcome]]
    completed <- !is.na(risk)
    data.frame(pairs=nrow(rows), completed=sum(completed), missing=sum(!completed),
               observed=if(any(completed)) mean(risk[completed]) else NA_real_,
               mean_gap=if(any(completed)) mean(rows$gap_before_sec[completed]) else NA_real_)
  })
  if (!length(result)) return(data.frame())
  data.frame(gap=names(result), do.call(rbind, unname(result)), row.names=NULL)
}

ui <- fluidPage(
  titlePanel("F1 undercut window"),
  p(if (fake) "Synthetic handoff fixture for software testing." else if (draft)
    "Draft logistic fit using 2018–2023 training races." else "Observed comparison data use 2018–2023 training races."),
  p("Success means the chaser is ahead at the common lap and at each of the next three lap boundaries."),
  fluidRow(column(4, selectInput("delay","Rival stop delay",delays)),
           column(4, selectInput("model","Model",unique(window$model_id),
                                 selected=if ("draft_gap_plus_delay" %in% window$model_id) "draft_gap_plus_delay" else NULL))),
  plotOutput("window",height="360px"),
  tableOutput("gap_rates"),
  fluidRow(column(7,h3("Observed comparison groups"),tableOutput("comparison")),
           column(5,h3("Rival no-response rate"),textOutput("no_response"))),
  h3("Historical examples"), tableOutput("examples")
)

server <- function(input, output, session) {
  cases <- reactive(subset(core, delay_group==input$delay))
  gap_rates <- reactive(gap_summary(cases()))
  output$window <- renderPlot({
    validate(need(nrow(window)>0,"Common-lap model predictions are pending."),
             need(nrow(cases())>0,"No training cases for this delay."))
    known <- cases()[!is.na(cases()[[outcome]]), ]
    validate(need(nrow(known)>0,"Common-lap follow-up is unavailable for this delay."))
    w <- subset(window, model_id==input$model & delay_group==input$delay)
    limits <- range(known$gap_before_sec)
    w <- w[order(w$gap_sec), ]
    w <- subset(w, gap_sec>=limits[1] & gap_sec<=limits[2])
    validate(need(nrow(w)>1,"Model curve unavailable inside the observed starting gaps."))
    plot(w$gap_sec,w$p_success,type="n",ylim=c(0,1),
         xlab="Starting gap in seconds",ylab="Probability of staying ahead")
    abline(h=c(.25,.50),lty=3,col="gray55")
    if (all(is.finite(w$p_lo) & is.finite(w$p_hi))) {
      polygon(c(w$gap_sec,rev(w$gap_sec)),c(w$p_lo,rev(w$p_hi)),col="#d9e8f4",border=NA)
    }
    lines(w$gap_sec,w$p_success,col="#234964",lwd=2)
    rates <- gap_rates()
    points(rates$mean_gap,rates$observed,pch=19,col="#9d4d23")
    legend("topright",c("Model probability","Observed gap bands"),col=c("#234964","#9d4d23"),
           lty=c(1,NA),pch=c(NA,19),bty="n")
  })
  output$gap_rates <- renderTable({
    rates <- gap_rates()
    validate(need(nrow(rates)>0,"No observed gap bands for this delay."))
    rates$mean_gap <- NULL
    rates
  },digits=3,na="Unavailable")
  output$comparison <- renderTable({
    do.call(rbind,lapply(names(labels), function(group) {
      values <- pairs[[outcome]][pairs$delay_group==group & !is.na(pairs$delay_group)]
      n <- sum(!is.na(values))
      data.frame(Group=labels[[group]],Pairs=length(values),Completed=n,
                 Observed=if(n) mean(values,na.rm=TRUE) else NA_real_)
    }))
  },digits=3,na="Unavailable")
  output$no_response <- renderText({
    count <- if (is.null(no_response)) NULL else nrow(subset(no_response,
      year %in% 2018:2023 & clean_window==1 & teammates==0 & gap_before_sec>0 & gap_before_sec<=6))
    paste("Rate unavailable until the eligible-opportunity denominator is agreed.",
          if (!is.null(count)) paste(count,"eligible no-response records in the supplied file."))
  })
  output$examples <- renderTable({
    validate(need(!fake,"Historical examples are unavailable in the synthetic fixture."))
    observed <- subset(cases(), !is.na(success_common_h3))
    observed <- observed[order(abs(observed$gap_before_sec-2),observed$battle_id), ]
    shown <- observed[!duplicated(observed[[outcome]]), ]
    validate(need(nrow(shown)>0,"No complete historical examples for this delay."))
    data.frame(Race=shown$event_id,Chaser=shown$chaser,Rival=shown$leader,
               Starting_gap=shown$gap_before_sec,Common_lap=shown$common_lap,
               Stayed_ahead=ifelse(shown[[outcome]]==1,"Yes","No"))
  },digits=2)
}

shinyApp(ui,server)
