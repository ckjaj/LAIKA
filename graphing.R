
#### takes command line input of the filename in the DATA folder


library("ggplot2")

get_csv_path <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  
  if (length(args) == 0) {
    stop("No file specified. Usage: Rscript script.R <filename.csv>")
  }
  
  csv_path <- args[1]
  
  # if they didn't include DATA/ prefix, add it
  if (!startsWith(csv_path, "DATA/")) {
    csv_path <- file.path("DATA", csv_path)
  }
  
  if (!file.exists(csv_path)) {
    stop(paste("File not found:", csv_path))
  }
  
  if (tolower(tools::file_ext(csv_path)) != "csv") {
    stop(paste("File is not a CSV:", csv_path))
  }
  
  return(csv_path)
}

csv_path <- get_csv_path()
data <- read.csv(csv_path, header=TRUE)

alt_graph <- ggplot(data, aes(x=rel_time, y=rel_altitude)) +
  geom_line( color="steelblue") + 
  geom_point()

# If a folder named 'output' exists in your working directory
ggsave(filename = "output/graph.png", plot = alt_graph)
