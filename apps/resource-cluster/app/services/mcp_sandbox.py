"""
MCP Sandbox Service for GT 2.0

Provides secure sandboxed execution environment for MCP servers.
Implements resource isolation, monitoring, and security constraints.
"""

import os
import asyncio
import resource
import signal
import tempfile
import shutil
from typing import Dict, Any, Optional, Callable, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import logging
import json
import psutil
from contextlib import asynccontextmanager
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SandboxConfig:
    """Configuration for sandbox environment"""
    # Resource limits
    max_memory_mb: int = 512
    max_cpu_percent: int = 50
    max_disk_mb: int = 100
    timeout_seconds: int = 30
    
    # Security settings
    network_isolation: bool = True
    readonly_filesystem: bool = False
    allowed_paths: list = None
    blocked_paths: list = None
    allowed_commands: list = None
    
    # Process limits
    max_processes: int = 10
    max_open_files: int = 100
    max_threads: int = 20
    
    def __post_init__(self):
        if self.allowed_paths is None:
            self.allowed_paths = ["/tmp", "/var/tmp"]
        if self.blocked_paths is None:
            self.blocked_paths = ["/etc", "/root", "/home", "/usr/bin", "/usr/sbin"]
        if self.allowed_commands is None:
            self.allowed_commands = ["ls", "cat", "grep", "find", "echo", "pwd"]


class ProcessSandbox:
    """
    Process-level sandbox for MCP tool execution
    Uses OS-level isolation and resource limits
    """
    
    def __init__(self, config: SandboxConfig):
        self.config = config
        self.process: Optional[asyncio.subprocess.Process] = None
        self.start_time: Optional[datetime] = None
        self.temp_dir: Optional[Path] = None
        self.resource_monitor_task: Optional[asyncio.Task] = None
    
    async def __aenter__(self):
        """Enter sandbox context"""
        await self.setup()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit sandbox context and cleanup"""
        await self.cleanup()
    
    async def setup(self):
        """Setup sandbox environment"""
        # Create temporary directory for sandbox
        self.temp_dir = Path(tempfile.mkdtemp(prefix="mcp_sandbox_"))
        os.chmod(self.temp_dir, 0o700)  # Restrict access
        
        # Set resource limits for child processes
        self._set_resource_limits()
        
        # Start resource monitoring
        self.resource_monitor_task = asyncio.create_task(self._monitor_resources())
        
        self.start_time = datetime.utcnow()
        logger.info(f"Sandbox setup complete: {self.temp_dir}")
    
    async def cleanup(self):
        """Cleanup sandbox environment"""
        # Stop resource monitoring
        if self.resource_monitor_task:
            self.resource_monitor_task.cancel()
            try:
                await self.resource_monitor_task
            except asyncio.CancelledError:
                pass
        
        # Terminate process if still running
        if self.process and self.process.returncode is None:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
        
        # Remove temporary directory
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        logger.info("Sandbox cleanup complete")
    
    async def execute(
        self,
        command: str,
        args: list = None,
        input_data: str = None,
        env: Dict[str, str] = None
    ) -> Tuple[int, str, str]:
        """
        Execute command in sandbox
        
        Args:
            command: Command to execute
            args: Command arguments
            input_data: Input to send to process
            env: Environment variables
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        # Validate command
        if not self._validate_command(command):
            raise PermissionError(f"Command not allowed: {command}")
        
        # Prepare environment
        sandbox_env = self._prepare_environment(env)
        
        # Prepare command with arguments
        full_command = [command] + (args or [])
        
        try:
            # Create process with resource limits
            self.process = await asyncio.create_subprocess_exec(
                *full_command,
                stdin=asyncio.subprocess.PIPE if input_data else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.temp_dir),
                env=sandbox_env,
                preexec_fn=self._set_process_limits if os.name == 'posix' else None
            )
            
            # Execute with timeout
            stdout, stderr = await asyncio.wait_for(
                self.process.communicate(input=input_data.encode() if input_data else None),
                timeout=self.config.timeout_seconds
            )
            
            return self.process.returncode, stdout.decode(), stderr.decode()
            
        except asyncio.TimeoutError:
            if self.process:
                self.process.kill()
                await self.process.wait()
            raise TimeoutError(f"Command exceeded {self.config.timeout_seconds}s timeout")
        except Exception as e:
            logger.error(f"Sandbox execution error: {e}")
            raise
    
    async def execute_function(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute Python function in sandbox
        Uses multiprocessing for isolation
        """
        import multiprocessing
        import pickle
        
        # Create pipe for communication
        parent_conn, child_conn = multiprocessing.Pipe()
        
        def sandbox_wrapper(conn, func, args, kwargs):
            """Wrapper to execute function in child process"""
            try:
                # Apply resource limits
                self._set_process_limits()
                
                # Execute function
                result = func(*args, **kwargs)
                
                # Send result back
                conn.send(("success", pickle.dumps(result)))
            except Exception as e:
                conn.send(("error", str(e)))
            finally:
                conn.close()
        
        # Create and start process
        process = multiprocessing.Process(
            target=sandbox_wrapper,
            args=(child_conn, func, args, kwargs)
        )
        process.start()
        
        # Wait for result with timeout
        try:
            if parent_conn.poll(self.config.timeout_seconds):
                status, data = parent_conn.recv()
                if status == "success":
                    return pickle.loads(data)
                else:
                    raise RuntimeError(f"Sandbox function error: {data}")
            else:
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()
                raise TimeoutError(f"Function exceeded {self.config.timeout_seconds}s timeout")
        finally:
            parent_conn.close()
            if process.is_alive():
                process.terminate()
                process.join()
    
    def _validate_command(self, command: str) -> bool:
        """Validate if command is allowed"""
        # Check if command is in allowed list
        command_name = os.path.basename(command)
        if self.config.allowed_commands and command_name not in self.config.allowed_commands:
            return False
        
        # Check for dangerous patterns
        dangerous_patterns = [
            "rm -rf",
            "dd if=",
            "mkfs",
            "format",
            ">",  # Redirect that could overwrite files
            "|",  # Pipe that could chain commands
            ";",  # Command separator
            "&",  # Background execution
            "`",  # Command substitution
            "$("  # Command substitution
        ]
        
        for pattern in dangerous_patterns:
            if pattern in command:
                return False
        
        return True
    
    def _prepare_environment(self, custom_env: Dict[str, str] = None) -> Dict[str, str]:
        """Prepare sandboxed environment variables"""
        # Start with minimal environment
        sandbox_env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": str(self.temp_dir),
            "TEMP": str(self.temp_dir),
            "TMP": str(self.temp_dir),
            "USER": "sandbox",
            "SHELL": "/bin/sh"
        }
        
        # Add custom environment variables if provided
        if custom_env:
            # Filter out dangerous variables
            dangerous_vars = ["LD_PRELOAD", "LD_LIBRARY_PATH", "PYTHONPATH", "PATH"]
            for key, value in custom_env.items():
                if key not in dangerous_vars:
                    sandbox_env[key] = value
        
        return sandbox_env
    
    def _set_resource_limits(self):
        """Set resource limits for the process"""
        if os.name != 'posix':
            return  # Resource limits only work on POSIX systems
        
        # Memory limit
        memory_bytes = self.config.max_memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        
        # CPU time limit
        resource.setrlimit(resource.RLIMIT_CPU, (self.config.timeout_seconds, self.config.timeout_seconds))
        
        # File size limit
        file_size_bytes = self.config.max_disk_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_FSIZE, (file_size_bytes, file_size_bytes))
        
        # Process limit
        resource.setrlimit(resource.RLIMIT_NPROC, (self.config.max_processes, self.config.max_processes))
        
        # Open files limit
        resource.setrlimit(resource.RLIMIT_NOFILE, (self.config.max_open_files, self.config.max_open_files))
    
    def _set_process_limits(self):
        """Set limits for child process (called in child context)"""
        if os.name != 'posix':
            return
        
        # Drop privileges if running as root (shouldn't happen in production)
        if os.getuid() == 0:
            os.setuid(65534)  # nobody user
            os.setgid(65534)  # nogroup
        
        # Set resource limits
        self._set_resource_limits()
        
        # Set process group for easier cleanup
        os.setpgrp()
    
    async def _monitor_resources(self):
        """Monitor resource usage of sandboxed process"""
        while True:
            try:
                if self.process and self.process.returncode is None:
                    # Get process info
                    try:
                        proc = psutil.Process(self.process.pid)
                        
                        # Check CPU usage
                        cpu_percent = proc.cpu_percent(interval=0.1)
                        if cpu_percent > self.config.max_cpu_percent:
                            logger.warning(f"Sandbox CPU usage high: {cpu_percent}%")
                            # Could throttle or terminate if consistently high
                        
                        # Check memory usage
                        memory_info = proc.memory_info()
                        memory_mb = memory_info.rss / (1024 * 1024)
                        if memory_mb > self.config.max_memory_mb:
                            logger.warning(f"Sandbox memory limit exceeded: {memory_mb}MB")
                            self.process.terminate()
                            break
                        
                        # Check runtime
                        if self.start_time:
                            runtime = (datetime.utcnow() - self.start_time).total_seconds()
                            if runtime > self.config.timeout_seconds:
                                logger.warning(f"Sandbox timeout exceeded: {runtime}s")
                                self.process.terminate()
                                break
                    
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass  # Process ended or inaccessible
                
                await asyncio.sleep(1)  # Check every second
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Resource monitoring error: {e}")
                await asyncio.sleep(1)


class ContainerSandbox:
    """
    Container-based sandbox for stronger isolation
    Uses Docker or Podman for execution
    """
    
    def __init__(self, config: SandboxConfig):
        self.config = config
        self.container_id: Optional[str] = None
        self.container_runtime = self._detect_container_runtime()
    
    def _detect_container_runtime(self) -> str:
        """Detect available container runtime"""
        # Try Docker first
        if shutil.which("docker"):
            return "docker"
        # Try Podman as alternative
        elif shutil.which("podman"):
            return "podman"
        else:
            logger.warning("No container runtime found, falling back to process sandbox")
            return None
    
    @asynccontextmanager
    async def create_container(self, image: str = "alpine:latest"):
        """Create and manage container lifecycle"""
        if not self.container_runtime:
            raise RuntimeError("No container runtime available")
        
        try:
            # Create container with resource limits
            create_cmd = [
                self.container_runtime, "create",
                "--rm",  # Auto-remove after stop
                f"--memory={self.config.max_memory_mb}m",
                f"--cpus={self.config.max_cpu_percent / 100}",
                "--network=none" if self.config.network_isolation else "--network=bridge",
                "--read-only" if self.config.readonly_filesystem else "",
                f"--tmpfs=/tmp:size={self.config.max_disk_mb}m",
                "--security-opt=no-new-privileges",
                "--cap-drop=ALL",  # Drop all capabilities
                image,
                "sleep", "infinity"  # Keep container running
            ]
            
            # Remove empty strings from command
            create_cmd = [arg for arg in create_cmd if arg]
            
            # Create container
            proc = await asyncio.create_subprocess_exec(
                *create_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                raise RuntimeError(f"Failed to create container: {stderr.decode()}")
            
            self.container_id = stdout.decode().strip()
            
            # Start container
            start_cmd = [self.container_runtime, "start", self.container_id]
            proc = await asyncio.create_subprocess_exec(*start_cmd)
            await proc.wait()
            
            logger.info(f"Container sandbox created: {self.container_id[:12]}")
            
            yield self
            
        finally:
            # Cleanup container
            if self.container_id:
                stop_cmd = [self.container_runtime, "stop", self.container_id]
                proc = await asyncio.create_subprocess_exec(*stop_cmd)
                await proc.wait()
                
                logger.info(f"Container sandbox cleaned up: {self.container_id[:12]}")
    
    async def execute(self, command: str, args: list = None) -> Tuple[int, str, str]:
        """Execute command in container"""
        if not self.container_id:
            raise RuntimeError("Container not created")
        
        exec_cmd = [
            self.container_runtime, "exec",
            self.container_id,
            command
        ] + (args or [])
        
        proc = await asyncio.create_subprocess_exec(
            *exec_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.timeout_seconds
            )
            return proc.returncode, stdout.decode(), stderr.decode()
        except asyncio.TimeoutError:
            # Kill process in container
            kill_cmd = [self.container_runtime, "exec", self.container_id, "kill", "-9", "-1"]
            await asyncio.create_subprocess_exec(*kill_cmd)
            raise TimeoutError(f"Command exceeded {self.config.timeout_seconds}s timeout")


# Factory function to get appropriate sandbox
def create_sandbox(config: SandboxConfig, prefer_container: bool = True) -> Any:
    """
    Create appropriate sandbox based on availability and preference
    
    Args:
        config: Sandbox configuration
        prefer_container: Prefer container over process sandbox
        
    Returns:
        ProcessSandbox or ContainerSandbox instance
    """
    if prefer_container and shutil.which("docker"):
        return ContainerSandbox(config)
    elif prefer_container and shutil.which("podman"):
        return ContainerSandbox(config)
    else:
        return ProcessSandbox(config)