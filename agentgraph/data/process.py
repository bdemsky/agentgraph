import subprocess
from agentgraph.core.mutable import Mutable
from typing import Optional, List

class Process(Mutable):
    def __init__(self, path: str, cmd: Optional[str] = None, args: Optional[List[str]] = None):
        super().__init__(None)
        if args is not None:
            self.args = args
        else:
            self.args=cmd.split()
        self.cmd = cmd
        self.process = subprocess.Popen(self.args, cwd=path, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def wait(self, timeout = None):
        self.wait_for_access()
        self.process.wait(timeout)

    def kill(self):
        self.wait_for_access()
        self.process.kill()

    def send_input(self, input: str):
        self.wait_for_access()
        self.process.stdin.write(bytes(input, 'utf-8'))
        self.process.stdin.flush()

    def get_output(self):
        self.wait_for_access()
        return self.process.stdout.read1()

