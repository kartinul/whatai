import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export async function runCommand(command: string): Promise<string> {
    try {
        const { stdout, stderr } = await execAsync(command, { timeout: 15000 });
        return (stdout || stderr || 'done').trim();
    } catch (error: any) {
        if (error.killed) {
            return 'timed out';
        }
        return `error: ${error.message}`;
    }
}
