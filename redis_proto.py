


def decoder(p):

    leng = 0
    i=1
    while (p[i] != '\r') :

        leng = (leng * 10)+( p - '0')
        i+=1


    return leng