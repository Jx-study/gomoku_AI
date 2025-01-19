from graphics import*

def main():
    window = GraphWin("gomoku", 800, 800) # windowName, length, height
    window.setBackground(color_rgb(0, 0, 0)) # red, green, blue(0~255)
    img = Image(Point(400, 400), "200w.gif")
    img.draw(window)

    txt = Text(Point(400,50), "Hello World!!!")
    txt.setTextColor("white")
    txt.setSize(30)
    txt.setFace('courier')
    txt.setStyle("bold")
    txt.draw(window)

    # create object
    input_box = Entry(Point(400, 300), 10)
    input_box.draw(window)
    notice = Text(Point(400,100), '')
    notice.setTextColor('red')
    notice.draw(window)

    # get text
    while True:
        notice.setText(input_box.getText())


    window.getMouse()
    window.close()

main()