OUTPUT_PATH = "./outputPillow.png"
INPUT_IMAGE_PATH = "./input.png"
FONT_PATH = "./Barlow-Regular.ttf"
BOLD_FONT_PATH = "./Barlow-Bold.ttf"

# import pygame
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import io
# import math

# pygame.font.init()
# font = pygame.font.Font(FONT_PATH,50)
font = PIL.ImageFont.truetype(FONT_PATH,50)
# fontBold = pygame.font.Font(BOLD_FONT_PATH,50)
fontBold = PIL.ImageFont.truetype(BOLD_FONT_PATH,50)

image1 = PIL.Image.open(INPUT_IMAGE_PATH)
image1.load()
with open(INPUT_IMAGE_PATH,"rb") as f:
    image2 = PIL.Image.open(f)
    image2.load()
with open(INPUT_IMAGE_PATH,"rb") as f:
    with io.BytesIO(f.read()) as buffer:
        image3 = PIL.Image.open(buffer)
        image3.load()
result1 = True
for x in range(image1.width):
    for y in range(image1.height):
        if (image1.getpixel((x,y)) != (px2:=image2.getpixel((x,y)))) or (px2 != image3.getpixel((x,y))):
            result1 = False
print(result1)

print(image1.getpixel((26,33)) == (33,28,40,198))

imageResult2 = PIL.Image.new("RGBA",(500,500))

print(imageResult2.getpixel((0,0)) == (0,0,0,0))

draw = PIL.ImageDraw.Draw(imageResult2)
# pygame.draw.rect(imageResult2,(0,0,0),pygame.Rect(250,0,250,500),50,20)
draw.rounded_rectangle((250,0,250+250-1,0+500-1),20,None,(0,0,0),50)
# pygame.draw.circle(imageResult2,(127,127,127,127),(250,250),225)
draw.ellipse((250-225,250-225,250+225,250+225),(127,127,127,127))
# pygame.draw.circle(imageResult2,(255,0,0),(250,250),200,draw_top_right=True)
draw.arc((250-200,250-200,250+200-1,250+200-1),270,0,(255,0,0),200)
# pygame.draw.arc(imageResult2,(127,0,0),pygame.Rect(50,50,400,400),0,math.radians(22.5),200)
draw.arc((50,50,50+400-1,50+400-1),360-22.5,0,(127,0,0),200)
# pygame.draw.arc(imageResult2,(127,0,0),pygame.Rect(50,50,400,400),math.radians(45),math.radians(67.5),200)
draw.arc((50,50,50+400-1,50+400-1),360-67.5,360-45,(127,0,0),200)
# pygame.draw.circle(imageResult2,(187,187,187),(250,250),200,100,draw_top_left=True,draw_bottom_left=True,draw_bottom_right=True)
draw.arc((250-200,250-200,250+200-1,250+200-1),0,270,(187,187,187),100)
# text1 = font.render("Qabc",1,(255,255,255),(0,0,0))
# imageResult2.blit(text1,(0,0))
text1Size = font.getbbox("Qabc")
text1 = PIL.Image.new("RGBA",(text1Size[2]+1,text1Size[3]+1),(0,0,0))
draw1 = PIL.ImageDraw.Draw(text1)
draw1.text((0,0),"Qabc",(255,255,255),font)
imageResult2.paste(text1,(0,0))
# text2 = fontBold.render("Qabc",1,(255,255,255))
# imageResult2.blit(text2,(text1.get_width(),0))
text2Size = font.getbbox("Qabc")
text2 = PIL.Image.new("RGBA",(text2Size[2]+1,text2Size[3]+1))
draw2 = PIL.ImageDraw.Draw(text2)
draw2.text((0,0),"Qabc",(255,255,255),fontBold)
imageResult2.paste(text2,(text1.width,0),text2)
# pygame.draw.polygon(imageResult2,(0,255,0),[(250,250),(250,350),(150,250)])
draw.polygon([(250,250),(250,350),(150,250)],(0,255,0))
# pygame.draw.line(imageResult2,(0,0,255),(123,456),(321,300),10)
draw.line([(123,456),(321,300)],(0,0,255),10)
# imageResult2 = pygame.transform.smoothscale(imageResult2,(400,400))
imageResult2 = imageResult2.resize((400,400))
# imageResult2 = pygame.transform.rotate(imageResult2,45)
imageResult2 = imageResult2.rotate(45,expand=True)

with io.BytesIO() as buffer1:
    imageResult2.save(buffer1,"png")
    buffer2 = io.BytesIO(buffer1.getvalue())
with open(OUTPUT_PATH,"wb") as f:
    f.write(buffer2.getvalue())
print(True)