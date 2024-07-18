import subprocess

def initFile(filename, text):
    with open(filename, 'r+') as file:
        lines = file.readlines()
        lines[0] = text + '\n'
        file.seek(0)
        file.writelines(lines)
        file.truncate()

# Initialize files A.txt and B.txt with the letter 'R'
initFile('A.txt', 'R')
initFile('B.txt', 'R')

def compileC(source_file1, source_file2, source_file3, output_file):
    subprocess.run(['gcc', source_file1, source_file2, source_file3, '-o', output_file], check=True)

# Compile playerA and playerB executables
compileC('player.c', 'chessData.c', 'writeBack.c', 'playerA')
compileC('player.c', 'chessData.c', 'writeBack2.c', 'playerB')

# Start the chess.py process
chessProcess = subprocess.Popen(['python', 'chess.py'], stdin=subprocess.PIPE)
chessProcess.stdin.write(b'A.txt\nB.txt\n')
chessProcess.stdin.close()

# Start the playerA process
playerAProcess = subprocess.Popen(['./playerA'], stdin=subprocess.PIPE)
playerAProcess.stdin.write(b'A.txt\nA\n')
playerAProcess.stdin.close()

# Start the playerB process
playerBProcess = subprocess.Popen(['./playerB'], stdin=subprocess.PIPE)
playerBProcess.stdin.write(b'B.txt\nB\n')
playerBProcess.stdin.close()

# Wait for all processes to complete
chessProcess.wait()
playerAProcess.wait()
playerBProcess.wait()
