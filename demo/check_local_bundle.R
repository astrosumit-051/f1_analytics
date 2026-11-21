# Package checks: no real model or protected outcomes are evaluated.
a<-commandArgs(TRUE);bundle<-normalizePath(a[1],winslash='/')
env<-new.env(parent=globalenv());sys.source(file.path(bundle,'app.R'),envir=env,chdir=TRUE)
stopifnot(is.null(env$data$error),nrow(env$data$core)==564,all(env$data$pairs$split=='train'))
shiny::testServer(env$server, {
 session$setInputs(model='Model pending',outcome='success_common_h3',delay='d1',gap=2,compare_delays=TRUE)
 stopifnot(is.na(snapshot()$value$probability),nrow(snapshot()$comparison)==4,
   nchar(output$comparison)>0,nchar(output$examples)>0,nchar(output$no_response)>0)
 session$setInputs(delay='d23',gap=3)
 stopifnot(all(snapshot()$cases$delay_group=='d23'),nchar(output$gap_rates)>0)
})
cat('PACKAGED APP ASSERTIONS PASSED: 564 core training pairs, both delays and observed tables; model remains pending\n')
