import subprocess
import time

def initFile(filename, text):
    with open(filename, 'r+') as file:
        lines = file.readlines()
        lines[0] = text + '\n'
        file.seek(0)
        file.writelines(lines)
        file.truncate()

initFile('A.txt', 'R')
initFile('B.txt', 'R')

def compileC(source_file, output_file):
    subprocess.run(['gcc', source_file, '-o', output_file], check=True)

compileC('playerA_test.c', 'playerA_test')
compileC('playerB.c', 'playerB')

chessProcess = subprocess.Popen(['python', 'chess.py'], stdin=subprocess.PIPE)
chessProcess.stdin.write(b'A.txt\nB.txt\n')
chessProcess.stdin.close()

playerAProcess = subprocess.Popen(['./playerA_test'], stdin=subprocess.PIPE)
playerAProcess.stdin.write(b'A.txt\nA\n')
playerAProcess.stdin.close()

playerBProcess = subprocess.Popen(['./playerB'], stdin=subprocess.PIPE)
playerBProcess.stdin.write(b'B.txt\nB\n')
playerBProcess.stdin.close()

chessProcess.wait()
playerAProcess.wait()
playerBProcess.wait()
