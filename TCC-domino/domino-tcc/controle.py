import pygame
from pygame.locals import *
from sys import exit

pygame.init() #iniciar 

altura = 640
largura = 480
x = largura/2 
y = altura/2


tela = pygame.display.set_mode((altura, largura)) #define o tamanho da tela
pygame.display.set_caption('Dominó') #nome da tela
relogio = pygame.time.Clock()

while True: #faz com que o jogo não trave

    relogio.tick(1024)
    tela.fill((0,0,0))
    for event in pygame.event.get():
        if event.type == QUIT:
            pygame.quit()
            exit()
        if event.type == KEYDOWN:
            if event.key == K_a:
                x = x - 20
            if event.key == K_d:
                x = x + 20
            if event.key == K_w:
                y = y - 20
            if event.key == K_s:
                y = y + 20
    pygame.draw.rect(tela , (105, 30, 55), (x, y, 50, 60))
 

    pygame.display.update()