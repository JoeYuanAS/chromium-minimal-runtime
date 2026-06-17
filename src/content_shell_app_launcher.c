#include <errno.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int has_log_file_arg(int argc, char** argv) {
  for (int i = 1; i < argc; ++i) {
    if (strncmp(argv[i], "--log-file", 10) == 0)
      return 1;
  }
  return 0;
}

int main(int argc, char** argv) {
  char executable_path[PATH_MAX];
  uint32_t executable_path_size = sizeof(executable_path);
  if (_NSGetExecutablePath(executable_path, &executable_path_size) != 0) {
    fprintf(stderr, "Content Shell launcher path is too long\n");
    return 1;
  }

  char resolved_path[PATH_MAX];
  if (realpath(executable_path, resolved_path) == NULL) {
    perror("realpath");
    return 1;
  }

  char* last_slash = strrchr(resolved_path, '/');
  if (last_slash == NULL) {
    fprintf(stderr, "Content Shell launcher path has no directory\n");
    return 1;
  }
  *last_slash = '\0';

  char real_executable[PATH_MAX];
  int written = snprintf(real_executable, sizeof(real_executable),
                         "%s/Content Shell.bin", resolved_path);
  if (written < 0 || written >= (int)sizeof(real_executable)) {
    fprintf(stderr, "Content Shell real executable path is too long\n");
    return 1;
  }

  setenv("CHROME_LOG_FILE", "/tmp/content_shell.log", 0);

  int add_log_arg = !has_log_file_arg(argc, argv);
  char** child_argv =
      calloc((size_t)argc + (add_log_arg ? 2u : 1u), sizeof(char*));
  if (child_argv == NULL) {
    perror("calloc");
    return 1;
  }

  int out = 0;
  child_argv[out++] = real_executable;
  if (add_log_arg)
    child_argv[out++] = "--log-file=/tmp/content_shell.log";
  for (int i = 1; i < argc; ++i)
    child_argv[out++] = argv[i];
  child_argv[out] = NULL;

  execv(real_executable, child_argv);
  fprintf(stderr, "execv(%s) failed: %s\n", real_executable, strerror(errno));
  return 1;
}
