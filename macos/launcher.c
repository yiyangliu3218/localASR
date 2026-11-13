/*
 * Executable inside LocalASR.app. Starts `.venv/bin/python app.py` from the install
 * directory as a child process and waits for it.
 *
 * Why a compiled launcher instead of a shell script: macOS attributes the child's
 * permission requests (Microphone, Accessibility, Input Monitoring) to this app, so
 * the user grants them to "LocalASR" rather than to Python or a terminal.
 *
 * LOCALASR_DIR is baked in at build time by macos/make_app.sh.
 */
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

#ifndef LOCALASR_DIR
#error "build with -DLOCALASR_DIR=\"/path/to/localASR\""
#endif

#define MAX_LOG_BYTES (5 * 1024 * 1024)

extern char **environ;
static pid_t child = 0;

static void forward(int sig) {
    if (child > 0) kill(child, sig);
}

static void redirect_output(void) {
    const char *home = getenv("HOME");
    if (!home) return;
    char dir[1024], path[1100], old[1100];
    snprintf(dir, sizeof dir, "%s/Library/Logs/LocalASR", home);
    mkdir(dir, 0755);
    snprintf(path, sizeof path, "%s/LocalASR.log", dir);
    struct stat st;
    if (stat(path, &st) == 0 && st.st_size > MAX_LOG_BYTES) {
        snprintf(old, sizeof old, "%s/LocalASR.old.log", dir);
        rename(path, old);
    }
    int fd = open(path, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0) return;
    dup2(fd, STDOUT_FILENO);
    dup2(fd, STDERR_FILENO);
    close(fd);
}

int main(void) {
    redirect_output();
    if (chdir(LOCALASR_DIR) != 0) {
        fprintf(stderr, "[launcher] cannot open %s: %s\n", LOCALASR_DIR, strerror(errno));
        return 1;
    }
    setenv("PYTHONUNBUFFERED", "1", 1);

    struct sigaction sa = {0};
    sa.sa_handler = forward;  /* no SA_RESTART: waitpid below handles EINTR */
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGHUP, &sa, NULL);

    char *argv[] = {LOCALASR_DIR "/.venv/bin/python", "app.py", NULL};
    int rc = posix_spawn(&child, argv[0], NULL, NULL, argv, environ);
    if (rc != 0) {
        fprintf(stderr, "[launcher] cannot start %s: %s (re-run install.sh)\n", argv[0], strerror(rc));
        return 1;
    }
    int status;
    while (waitpid(child, &status, 0) < 0) {
        if (errno != EINTR) return 1;
    }
    if (WIFEXITED(status)) return WEXITSTATUS(status);
    return 128 + WTERMSIG(status);
}
