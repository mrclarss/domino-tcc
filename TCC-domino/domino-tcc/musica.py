import pygame
from pygame.locals import *
from sys import exit
from random import randint

pygame.init()

pygame.mixer.music.set_volume(0.1)
musica_de_fundo = pygame.mixer.music.load('BoxCat_Games_-_08_-_CPU_Talk.mp3')
barulho_colisao = pygame.mixer.Sound('smw_coin.wav')
pygame.mixer.music.play(-1)


largura = 640
altura = 480
x = largura/2
y = altura/2

x_azul = randint(40,600)
y_azul = randint(50,430)

pontos = 0
font = pygame.font.SysFont('arial', 30, True, True)

tela = pygame.display.set_mode((largura, altura))
pygame.display.set_caption('Jogo')
relogio = pygame.time.Clock()

while True:
    relogio.tick(30)
    tela.fill((0,0,0))
    mensagem = f'pontos: {pontos}'
    texto_formatado = font.render(mensagem, True, (255, 255, 255))
    for event in pygame.event.get():
        if event.type == QUIT:
            pygame.quit()
            exit()


    if pygame.key.get_pressed()[K_a]:
        x = x - 20
    if pygame.key.get_pressed()[K_d]:
        x = x + 20
    if pygame.key.get_pressed()[K_w]:
        y = y - 20
    if pygame.key.get_pressed()[K_s]:
        y = y + 20

    ret_vermelho = pygame.draw.rect(tela, (255,0, 0), (x,y,40,50))
    ret_azul = pygame.draw.rect(tela, (0,0, 255), (x_azul, y_azul, 40, 50))

    if ret_vermelho.colliderect(ret_azul):
        x_azul = randint(40, 600)
        y_azul = randint(50,430)
        pontos = pontos + 1
        barulho_colisao.play()

    tela.blit(texto_formatado,(450, 40))
    pygame.display.update()